#### 通信协议概览
TCP 也是流，为了不粘包，我们采用 **Length-Prefix (长度前缀)** 格式。
所有整数均使用 **Big-Endian (网络字节序)**。

#### 步骤 1：建立连接 & 发送协议头
在开始录音前，先发送一段 JSON 告诉服务端“我要开始发流式音频了”。

*   **数据结构：** `[4字节头长度]` + `[JSON字符串]`
*   **JSON关键字段：** `size: 0` (这告诉服务端进入流式接收模式)

**C++ 伪代码：**
```cpp
// 1. 准备 JSON
std::string json_str = "{\"type\":\"VOICE_COMMAND\", \"size\":0, \"sample_rate\":16000}";
int len = json_str.length();

// 2. 转换为网络字节序 (Big Endian)
uint32_t net_len = htonl(len); 

// 3. 发送长度
send(sock, &net_len, 4, 0);

// 4. 发送 JSON 数据
send(sock, json_str.c_str(), len, 0);
```

#### 步骤 2：流式发送音频 (循环中)
客户端每从麦克风读取一段 PCM 数据（例如 1024 字节），就立即封装发送。

*   **数据结构：** `[4字节本段长度]` + `[PCM数据]`

**C++ 伪代码：**
```cpp
char buffer[1024]; // 假设这是你从麦克风读到的数据
while (is_recording) {
    int bytes_read = capture_audio(buffer, 1024);
    if (bytes_read > 0) {
        // 1. 先发这段数据的长度
        uint32_t chunk_len = htonl(bytes_read);
        send(sock, &chunk_len, 4, 0);
        
        // 2. 再发实际数据
        send(sock, buffer, bytes_read, 0);
    }
}
```

#### 步骤 3：结束发送
当检测到静音或用户松开按钮时，发送一个长度为 0 的包，告知服务端传输结束。

*   **数据结构：** `[0000]` (4个字节的0)

**C++ 伪代码：**
```cpp
// 发送 0 表示结束
uint32_t end_signal = 0; // 0 不需要 htonl 也是 0
send(sock, &end_signal, 4, 0);

// 现在开始等待服务端 recv() 响应...
```

#### 总结：字节流长什么样？
假设你发了两次音频，一次 "Hi" (2字节)，一次 "AI" (2字节)，最后结束。
整个 TCP 就像这样：

```text
[HeaderLen][HeaderJSON] [Len=2][Hi] [Len=2][AI] [Len=0]
```

#### C++ 注意事项
1.  **Endianness**: 一定要用 `htonl()` 处理长度整数，因为 x86 架构通常是小端序，而网络协议（和你的 Python 服务端）通常期望大端序。
2.  **Socket Buffer**: 尽量关闭 Nagle 算法 (`TCP_NODELAY`)，这样小片段音频会发得更快，降低延迟。
    ```cpp
    int flag = 1;
    setsockopt(sock, IPPROTO_TCP, TCP_NODELAY, (char *)&flag, sizeof(int));
    ```