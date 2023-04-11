# This code is Apache 2 licensed:
# https://www.apache.org/licenses/LICENSE-2.0
import openai
import re
import httpx
from pystac_client import Client
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from opencage.geocoder import OpenCageGeocode
import json
import os

app = FastAPI()

if not 'OPENAI_API_KEY' in os.environ:
    raise Exception("OPENAI_API_KEY must be defined in your environment")

if not 'OPENCAGE_API_KEY' in os.environ:
    raise Exception("OPENCAGE_API_KEY is required")

openai.api_key = os.environ['OPENAI_API_KEY']
stac_endpoint = "https://planetarycomputer.microsoft.com/api/stac/v1"

geocoder_key = os.environ['OPENCAGE_API_KEY']
geocoder = OpenCageGeocode(geocoder_key)

app.mount("/templates", StaticFiles(directory="templates"), name="templates")

@app.get("/status")
def health():
    return {"status": "success"}

@app.get("/chatgpt")
async def chatgpt(prompt: str):
    return await query(prompt)


class ChatBot:
    def __init__(self, system=""):
        self.system = system
        self.messages = []
        if self.system:
            self.messages.append({"role": "system", "content": system})
    
    async def __call__(self, message):
        self.messages.append({"role": "user", "content": message})
        result = await self.execute()
        self.messages.append({"role": "assistant", "content": result})
        return result
    
    async def execute(self):
        completion = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=self.messages)
        # Uncomment this to print out token usage each time, e.g.
        # {"completion_tokens": 86, "prompt_tokens": 26, "total_tokens": 112}
        # print(completion.usage)
        return completion.choices[0].message.content

prompt = """
You run in a loop of Thought, Action, PAUSE, Observation.
At the end of the loop you output an Answer
Use Thought to describe your thoughts about the question you have been asked.
Use Action to run one of the actions available to you - then return PAUSE.
Observation will be the result of running those actions.

The questions will involve getting satellite imagery out of a STAC catalog.

To resolve the question, you have the following tools available that you can use.

Your available actions are:

calculate:
e.g. calculate: 4 * 7 / 3
Runs a calculation and returns the number - uses Python so be sure to use floating point syntax if necessary

wikipedia:
e.g. wikipedia: Mumbai
Returns a summary from searching Wikipedia

stac:
e.g. stac: bbox=[-73.21, 43.99, -73.12, 44.05] && datetime=['2019-01-01T00:00:00Z', '2019-01-02T00:00:00Z']
Will query the Microsoft Planetary Computer STAC endpoint for STAC records for that bbox and datetime and return a JSON representation of the item assets returned from the STAC API.
Please ensure the STAC query is entered exactly as above, with a bbox representing the lat / lng extents of the area.

and the datetime representing timestamps for start and end time to search the catalog within. Always return the rendered preview URL from the items.

Please remember that these are your only three available actions. Do not attempt to put any word after "Action: " other than wikipedia, calculate or stac. THIS IS A HARD RULE. DO NOT BREAK IT AT ANY COST. DO NOT MAKE UP YOUR OWN ACTIONS.

Always look things up on Wikipedia if you have the opportunity to do so.

Example session:

Question: Can you point me to satellite images for 2019 January, for the capital of France?
Thought: I should look up France on Wikipedia, find its capital, and find its bounding box extent.
Action: wikipedia: France
PAUSE

You will be called again with this:

Observation: France is a country. The capital is Paris. Its bbox is [27, 54, 63, 32.5]

You then output:

Thought: I should now query the STAC catalog to fetch data about satellite images of Paris.

Action: stac: bbox=[27, 54, 63, 32.5] && datetime=['2019-01-01T00:00:00Z', '2019-01-02T00:00:00Z']
PAUSE

You will be called again with the output from the STAC query as JSON. Use that to give the user information about what is available on STAC for their query.

""".strip()


action_re = re.compile('^Action: (\w+): (.*)$')

async def query(question, max_turns=5):
    i = 0
    bot = ChatBot(prompt)
    next_prompt = question
    while i < max_turns:
        i += 1
        result = await bot(next_prompt)
        print(result)
        actions = [action_re.match(a) for a in result.split('\n') if action_re.match(a)]
        if actions:
            # There is an action to run
            action, action_input = actions[0].groups()
            if action not in known_actions:
                raise Exception("Unknown action: {}: {}".format(action, action_input))
            print(" -- running {} {}".format(action, action_input))
            observation = await known_actions[action](action_input)
            print("Observation:", observation)

            # If the action is querying the STAC API, just return the results, don't re-prompt
            if action == 'stac':
                return observation
            else:
                next_prompt = "Observation: {}".format(observation)
        else:
            return result


async def stac(q):
    bbox_match = re.search(r'bbox=\[(.*?)\]', q)
    datetime_match = re.search(r'datetime=\[(.*?)\]', q)

    # Check if bbox and datetime arrays are found
    if bbox_match and datetime_match:
        bbox_str = bbox_match.group(1)
        datetime_str = datetime_match.group(1)

        # Remove spaces after commas, if any
        bbox_str = bbox_str.replace(', ', ',')
        datetime_str = datetime_str.replace(', ', ',')

        # Convert bbox and datetime arrays to lists
        bbox = [float(x) if '.' in x else int(x) for x in bbox_str.split(',')]
        datetime = [x.strip('\'') for x in datetime_str.split(',')]
    else:
        raise Exception("ChatGPT did a weirdo", q)

    print('datetime', datetime)
    api = Client.open(stac_endpoint)

    results = api.search(
        max_items=10,
        bbox=bbox,
        datetime=datetime,
    )
    return {
        'stac': results.item_collection_as_dict(),
        'bbox': bbox,
        'datetime': datetime
    }

async def wikipedia(q):
    async with httpx.AsyncClient() as client:
        response = await client.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query",
            "list": "search",
            "srsearch": q,
            "format": "json"
        })
        return response.json()["query"]["search"][0]["snippet"]

async def geocode(q):
    async with httpx.AsyncClient() as client:
        response = geocoder.geocode(q, no_annotations='1')
        if response and response['results']:
            return response['results'][0]['bounds']
        else:
            return None

def calculate(what):
    return eval(what)

known_actions = {
    "wikipedia": wikipedia,
    "calculate": calculate,
    "stac": stac
}
