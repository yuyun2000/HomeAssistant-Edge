import json
import re
from chat import ChatBot, system_prompt
from ha_control import control_light, control_curtain

class HomeAssistantController:
    def __init__(self, api_key, base_url, model):
        self.bot = ChatBot(
            api_key=api_key,
            base_url=base_url,
            model=model,
            system_message=system_prompt
        )
    
    def parse_response(self, response: str) -> dict:
        """Extract homeassistant command from LLM response"""
        pattern = r"```homeassistant\n({.*?})\n```"
        match = re.search(pattern, response, re.DOTALL)
        if not match:
            return None
        
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    
    def execute_command(self, command: dict):
        """Execute homeassistant command using ha_control"""
        if not command:
            return
        
        service = command.get("service")
        device = command.get("target_device")
        
        if not service or not device:
            print("Invalid command format")
            return
        
        # Map service to control function
        if service == "light.turn_on":
            control_light(device, "on")
        elif service == "light.turn_off":
            control_light(device, "off")
        elif service == "cover.open":
            control_curtain(device, "position", position=100)
        elif service == "cover.close":
            control_curtain(device, "position", position=0)
        else:
            print(f"Unsupported service: {service}")
    
    def run(self):
        """Main interactive loop"""
        print("Home Assistant Controller - Type 'exit' to quit")
        while True:
            user_input = input("\nYou: ")
            if user_input.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break
            
            # Get LLM response
            content = self.bot.chat(user_input)
            print(f"\nAssistant: {content}")
            
            # Parse and execute command
            command = self.parse_response(content)
            if command:
                print(f"Executing: {command}")
                self.execute_command(command)

if __name__ == "__main__":
    controller = HomeAssistantController(
        api_key="sk-",
        base_url="http://192.168.20.104:8000/v1",
        model="qwen2.5-1.5B-p1024-ha-ax650"
    )
    controller.run()
