# HomeAssistant Edge - AI-Powered Home Automation

HomeAssistant Edge is an intelligent home automation system that integrates with HomeAssistant to control smart devices using natural language. It features a fine-tuned 1.5B Qwen2.5 model running on an AX650 edge computing chip for fast, offline processing.

## Key Features
- Natural language control of lights, curtains, and other smart devices
- **Voice command support** (press-to-talk functionality)
- Offline processing on AX650 edge computing chip
- Fast response times with local inference
- Privacy-focused design (no cloud dependency)

## Technical Specifications
- **AI Model**: Qwen2.5-1.5B fine-tuned for home automation
- **Hardware**: AX650 edge computing chip
- **Inference Speed**: <100ms response time
- **Connectivity**: Local network only
- **ASR Integration**: Speech recognition via local API

## Setup Instructions

1. Install dependencies:
```bash
pip install -r requirements.txt
# Additional dependencies for voice control
pip install pyaudio keyboard
```

2. Configure your smart home devices in `ha_control.py`

3. Make sure the ASR server is running at http://192.168.20.104:8001/recognize

4. Start the interactive assistant:
```bash
python interactive_ha.py
```

## Usage Examples

### Voice Control
```bash
Press SPACE to start/stop recording
Recording started...
Recording stopped
You said: Turn on the living room lights
Assistant: I'll turn on the lights for you.
Executing: {'service': 'light.turn_on', 'target_device': 'light.livingroom'}

Press SPACE to start/stop recording
Recording started...
Recording stopped
You said: Open the bedroom curtains
Assistant: I'll open the curtains for you.
Executing: {'service': 'cover.open', 'target_device': 'cover.bedroom'}
```

### Text Input (Legacy)
```bash
You: Turn on the kitchen lights
Assistant: Turning on the kitchen lights
Executing: {'service': 'light.turn_on', 'target_device': 'light.kitchen'}
```

## System Architecture
```mermaid
graph TD
    A[User Voice] --> B(ASR Server)
    B --> C(HomeAssistant Edge)
    C --> D{Qwen2.5-1.5B Model}
    D --> E[Command Parsing]
    E --> F[Device Control]
    F --> G[Smart Home Devices]
    
    H[User Text] --> C
```

## Contributing
Contributions are welcome! Please open an issue or pull request on our GitHub repository.

## License
MIT License
