from dataclasses import dataclass
from typing import Dict
import openai
import json
import os
from pwn import log
from abc import ABC, abstractclassmethod
from dataclasses import dataclass
from typing import Any, List
from pwn import log
# from src.libs.colored import green_color
from colorama import Fore, Style

def green_color(text):
    return f'{Fore.GREEN}{text}{Style.RESET_ALL}'

def yellow_color(text):
    return f'{Fore.GREEN}{text}{Style.RESET_ALL}'

def cyan_color(text):
    return f'{Fore.CYAN}{text}{Style.RESET_ALL}'

openai.api_key = os.environ['OPENAI_API_KEY']

products = []
with open('src/calling_function_chatgpt/liquors.json', 'r') as file:
    products = json.load(file)

def get_products(search: str,limit: int = 10, offset: int = 0):
    filtered = []
    for p in products:
        if search.lower() in p['name'].lower() or search in p['description'].lower() or search.lower() in p['category'].lower():
            filtered.append(p)
    return json.dumps(filtered[offset:limit])

def get_categories():
    categories = []
    for c in list(map(lambda p: p['category'], products)):
        if c not in categories:
            categories.append(c)
    return json.dumps(categories)


@dataclass
class CallFunction(ABC):

    @property
    def manifest(self) -> Dict:
        ...

    @abstractclassmethod
    def execute(self, **kwargs):
        ...

    @property
    def function_name(self) -> str:
        return self.manifest["name"]



class ChatGPT:
    model = "gpt-3.5-turbo-0613"
    tokens = 0
    chat_status: Any = None
    
    def __init__(self, prompt: str, call_functions: list[CallFunction] ):
        self.call_functions = call_functions
        self.functions = list(map(lambda fn: fn.manifest, call_functions))
        self.messages = [{ 'role': 'system', 'content': prompt }]

    def add_message(self, message):
        self.messages.append(message)

    def update_token_usage(self, response):
        self.tokens += response['usage']['total_tokens']

    def execute_function(self, function_name, arguments):
        function_arguments = json.loads(arguments)
        for cf in self.call_functions:
            if cf.function_name == function_name:
                return cf.execute(**function_arguments)

    def get_answer(self, response):
        return response["choices"][0]["message"]["content"]

    def init_chat(self):
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=self.messages,
            functions=self.functions,
            function_call="auto",
            temperature=0
        )
        self.update_token_usage(response)
        return self.get_answer(response)
    
    def ask(self, input_message, temperature=0):
        self.add_message({ 'role': 'user', 'content': input_message })
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=self.messages,
            functions=self.functions,
            function_call="auto",
            temperature=temperature
        )
        self.update_token_usage(response)
        message = response["choices"][0]["message"]
        # verify function calling
        function_call = message.get("function_call")
        if function_call:
            # execute function
            function_name = function_call["name"]
            self.chat_status.status(f"Llamando a la funcion {function_name} {function_call['arguments']}")
            function_response = self.execute_function(function_name, function_call['arguments'])
            self.chat_status.status(f"{function_name}() ejecutada.")
            # update messages
            self.add_message(message)
            self.add_message({ "role": "function", "name": function_name, "content": function_response })
            # send messages to chatgpt
            second_response = openai.ChatCompletion.create(
                model=self.model,
                messages=self.messages,
                temperature=temperature
            )
            self.update_token_usage(second_response)
            return self.get_answer(second_response)
        # save message to context
        self.add_message(message)
        # no function calling 
        return self.get_answer(response)
    
    def progress(self, msg):
        self.chat_status = log.progress(msg)

    def status(self, msg):
        if self.chat_status:
            self.chat_status.status(msg)

    def success(self, msg):
        if self.chat_status:
            self.chat_status.success(msg)
    

def command_line(chatgpt: ChatGPT):
    
    try:
        print()
        assistant_progress = log.progress('AI Assistant')
        assistant_progress.status('Iniciando asistente...')
        assistant_input = chatgpt.init_chat()
        assistant_progress.success('Asistente listo!')
        while True:
            user_input = input(f"{green_color('[Assistant]')} {assistant_input}\n\n{green_color('[User]')} ")
            print()
            chatgpt.progress('Estado chat context')
            # exit command
            if user_input == 'exit':
                break
            # connecting with openai 
            chatgpt.status('Pensando...')
            assistant_input = chatgpt.ask(user_input)
            chatgpt.success("Listo!")

    except KeyboardInterrupt:
        log.info('Saliendo...')
    log.info(f'Total tokens: {chatgpt.tokens}\n')


class GetProductsCallFunction(CallFunction):
    manifest = {
        "name": "get_products",
        "description": "Obtiene los productos disponibles de la botilleria",
        "parameters": {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "busqueda por palabra clave",
                },
                "limit": {
                    "type": "number",
                    "description": "cantidad limite de datos a traer"
                },
                "offset": {
                    "type": "number",
                    "description": "indice donde empieza a traer datos"
                }
            }
          # "required": ["search"],
        }
    }

    def execute(self, **kwargs):
        return get_products(**kwargs)
    

class GetCategoriesCallFunction(CallFunction):
    manifest = {
        "name": "get_categories",
        "description": "Obtiene las categorias disponibles de la botilleria",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }

    def execute(self, **kwargs):
        return get_categories()
        
    

chatgpt = ChatGPT(
    prompt="""
    Se un util y amable asistente que resolvera consultas sobre sus productos existentes de una botillería. 
    [INSTRUCCIONES]: trabajaras con un limite de 15 items por consulta.
    [INSTRUCCIONES]: debes ser amable y gentil en tus respuestas.
    """,
    call_functions=[
        GetProductsCallFunction(),
        GetCategoriesCallFunction()
    ]
)

command_line(chatgpt=chatgpt)


# chatgpt.progress('Estado chat context')
# x = chatgpt.ask(input_message="""que cervezas tienes""")
# print(x)



