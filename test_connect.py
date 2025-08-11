from openai import OpenAI
client = OpenAI(
    api_key="sk-30cce8423d0c4f57a96108fbf22de0b0",
    base_url="http://192.168.20.188:8000/v1"
)

client.models.list()
print(client.models.list())  