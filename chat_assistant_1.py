import json
import markdown
import inspect

from openai import OpenAI
from IPython.display import display, HTML

def shorten(text, max_length=50):
    if len(text) <= max_length:
        return text

    return text[:max_length - 3] + "..."

class IPythonChatInterface:
    
    def input(self):
        question = input('User:').strip()
        return question

    def display(self, content):
        print(content)

    def display_function_call(self, entry, function_name, arguments, function_output):
        #function_name = entry.name
        #arguments = entry.arguments
        short_arguments = shorten(arguments)
        #function_output = call_output['output']

        call_html = f"""
            <details>
                <summary>Function call: <tt>{function_name}({short_arguments})</tt></summary>
                <div>
                    <b>Call</b>
                    <pre>{entry}</pre>
                </div>
                <div>
                    <b>Output</b>
                    <pre>{function_output}</pre>
                </div>
            
            </details>
        """
        display(HTML(call_html))
        
    
    def display_response(self, md_content):
        html_content = markdown.markdown(md_content)
        html = f"""
            <div>
                <div><b>Assistant:</b></div>
                <div>{html_content}</div>
            </div>
        """
        display(HTML(html))



def generate_description(func):
    """
    Generate a tool description schema for a given function using its
    docstring and signature.
    """
    # Get function name and docstring
    name = func.__name__
    doc = inspect.getdoc(func) or "No description provided."

    # Get function signature
    sig = inspect.signature(func)
    properties = {}
    required = []

    # Map Python types to JSON schema types
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object"
    }

    for param in sig.parameters.values():
        param_name = param.name
        param_annotation = param.annotation if param.annotation != inspect._empty else str
        param_type = type_map.get(param_annotation, "string")  # default to string
        properties[param_name] = {
            "type": param_type,
            "description": f"{param_name} parameter"
        }
        if param.default == inspect._empty:
            required.append(param_name)

    tool_description = {
        "type": "function",
        "name": name,
        "description": doc,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False
        }
    }

    return tool_description

class Tools:
    
    def __init__(self):
        self.tools = {}
        self.functions = {}
        
    def add_tool(self, function, description = None):
        """
            tool_schema = {
                "type": "function",
                "name": "function_name",
                "description": "What the function does",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "arg1": {
                            "type": "string",     # JSON Schema types
                            "description": "Meaning of arg1"
                        },
                        "arg2": {
                            "type": "integer",
                            "description": "Meaning of arg2"
                        } 
                    },
                    "required": ["arg1"],           # args the model must provide
                    "additionalProperties": False   # enforce no extra fields
                }
            }
        """
        if description == None:
            description =  generate_description(function)
        self.tools[function.__name__] = description
        self.functions[function.__name__] = function 

    def add_tools(self, instance):
        for name, member in inspect.getmembers(instance, predicate=inspect.ismethod):
            if not name.startswith('_'):
                self.add_tool(member)
        
    def get_tools(self):
        return list(self.tools.values()) 
        
    def funtion_call(self, tool_call_response):
        args = json.loads(tool_call_response.arguments)
        f_name = tool_call_response.name
        #f = globals()[f_name]  
        f = self.functions[f_name]
        call_id = tool_call_response.call_id
        results = f(**args)
        output_json = json.dumps(results)
        
        call_output = {
            "type": "function_call_output",
            "call_id": call_id,
            "output": output_json,
        }
        return call_output

class ChatAssistant:
    
    def __init__(self, tools, developer_prompt, interface, llm_client):
        self.developer_prompt = developer_prompt
        self.interface = interface
        self.llm_client = llm_client
        self.tools = tools
    
    def run(self): 
        
        chat_messages = [
            {"role": "developer", "content": self.developer_prompt},
        ]
        
        while True:
            question = self.interface.input()
        
            if question == 'stop':
                self.interface.display("Chat Ended")
                break
        
            chat_messages.append({"role": "user", "content": question})
            
            while True:
                response = self.llm_client.responses.create(
                    model='gpt-4o-mini',
                    input=chat_messages, 
                    tools=self.tools.get_tools()
                )
        
                has_funtion_call = False
                for entry in response.output:
                
                    chat_messages.append(entry)
                
                    if entry.type == 'message':
                        md_content = entry.content[0].text
                        self.interface.display_response(md_content)
                        #print('Assistant')
                        #print(entry.content[0].text)
                    if entry.type == 'function_call':
                        call_output = tools.funtion_call(entry)
                        
                        function_name = entry.name
                        arguments = entry.arguments
                        function_output = call_output['output']
        
                        self.interface.display_function_call(entry, function_name, arguments, function_output)
                        
                        chat_messages.append(call_output)
                        has_funtion_call =  True
                if not has_funtion_call:
                    break

