### Implement the ReAct pattern to connect an LLM with a STAC API endpoint

This is inspired by Simon Willison's blog-post: https://til.simonwillison.net/llms/python-react-pattern

The idea here is to develop a natural language interface to a STAC API endpoint, currently the Microsoft Planetary Computer STAC Catalog.

The code is currently very rudimentary and experimental, but already shows promising results.

### How to run

Create an environment variable called OPENAI_API_KEY with your OpenAI API key.

```
python

from main import query

> query("Can you get me satellite imagery for Seattle for 10th December, 2018?")

Observation: The STAC query returns a list of assets that are available for the given parameters of the bounding box and datetime, which includes imagery from NOAA GOES satellite (GLM-L2-LCFA/2018/345/00) as well as MODIS collection 6.1 (MYD21A2.A2018345.h09v04.061.2021350231530) which has several different assets available, including metadata and various thermal bands. The rendered preview image can be viewed at https://planetarycomputer.microsoft.com/api/data/v1/item/preview.png?collection=modis-21A2-061&item=MYD21A2.A2018345.h09v04.061.2021350231530&assets=LST_Day_1KM&tile_format=png&colormap_name=jet&rescale=255%2C310&format=png
```

In the above example, ChatGPT constructs queries to Wikipedia, gets the bounding box for Seattle, and uses that to construct a query to the STAC API for the bounding box and datetime requests. It currently only processes the first two results returned, but this can be easily improved.


### TODO

This is a very rough quick and dirty PoC. To improve this:

 - Move from wikipedia to using a real geocoder to fetch bounding boxes for a place
 - Allow it to use more complex STAC search functionality
 - Format the STAC search result object more appropriately to send back to ChatGPT for it to interpret results.
 - Augment ChatGPT's natural language answer with all the links, etc. from the actual STAC API response.



## Server setup
This is now wrapped in a lightweight FastAPI application

* `docker build -t fastapi-chatgpt-app .`
* `docker run -p 8000:8000 -e OPENAI_API_KEY=<your_openai_api_key> fastapi-chatgpt-app`
* Send a request like this: `http://localhost:8000/chatgpt?prompt=%22find%20me%20satellite%20imagery%20in%20Bangalore%20for%20December%2014,%202017%22`