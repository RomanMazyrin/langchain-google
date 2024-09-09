"""Util that calls Google Search."""

from typing import Any, Dict, List, Optional

from langchain_core.callbacks import CallbackManagerForToolRun
from pydantic import BaseModel, Extra, root_validator, model_validator
from langchain_core.tools import BaseTool
from langchain_core.utils import get_from_dict_or_env
from pydantic import ConfigDict



class GoogleSearchAPIWrapper(BaseModel):
    """Wrapper for Google Search API.

    Adapted from: Instructions adapted from https://stackoverflow.com/questions/
    37083058/
    programmatically-searching-google-in-python-using-custom-search

    TODO: DOCS for using it
    1. Install google-api-python-client
    - If you don't already have a Google account, sign up.
    - If you have never created a Google APIs Console project,
    read the Managing Projects page and create a project in the Google API Console.
    - Install the library using pip install google-api-python-client

    2. Enable the Custom Search API
    - Navigate to the APIs & Services→Dashboard panel in Cloud Console.
    - Click Enable APIs and Services.
    - Search for Custom Search API and click on it.
    - Click Enable.
    URL for it: https://console.cloud.google.com/apis/library/customsearch.googleapis
    .com

    3. To create an API key:
    - Navigate to the APIs & Services → Credentials panel in Cloud Console.
    - Select Create credentials, then select API key from the drop-down menu.
    - The API key created dialog box displays your newly created key.
    - You now have an API_KEY

    Alternatively, you can just generate an API key here:
    https://developers.google.com/custom-search/docs/paid_element#api_key

    4. Setup Custom Search Engine so you can search the entire web
    - Create a custom search engine here: https://programmablesearchengine.google.com/.
    - In `What to search` to search, pick the `Search the entire Web` option.
    After search engine is created, you can click on it and find `Search engine ID`
      on the Overview page.

    """

    search_engine: Any = None  #: :meta private:
    google_api_key: Optional[str] = None
    google_cse_id: Optional[str] = None
    k: int = 10
    siterestrict: bool = False

    model_config = ConfigDict(extra="forbid",)

    def _google_search_results(self, search_term: str, **kwargs: Any) -> List[dict]:
        cse = self.search_engine.cse()
        if self.siterestrict:
            cse = cse.siterestrict()
        res = cse.list(q=search_term, cx=self.google_cse_id, **kwargs).execute()
        return res.get("items", [])

    @model_validator(mode="after")
    def validate_environment(self) -> Self:
        """Validate that api key and python package exists in environment."""
        google_api_key = get_from_dict_or_env(
            values, "google_api_key", "GOOGLE_API_KEY"
        )
        self.google_api_key = google_api_key

        google_cse_id = get_from_dict_or_env(values, "google_cse_id", "GOOGLE_CSE_ID")
        self.google_cse_id = google_cse_id

        try:
            from googleapiclient.discovery import build  # type: ignore[import]

        except ImportError:
            raise ImportError(
                "google-api-python-client is not installed. "
                "Please install it with `pip install langchain-google-community`"
            )

        service = build("customsearch", "v1", developerKey=google_api_key)
        self.search_engine = service

        return self

    def run(self, query: str) -> str:
        """Run query through GoogleSearch and parse result."""
        snippets = []
        results = self._google_search_results(query, num=self.k)
        if len(results) == 0:
            return "No good Google Search Result was found"
        for result in results:
            if "snippet" in result:
                snippets.append(result["snippet"])

        return " ".join(snippets)

    def results(
        self,
        query: str,
        num_results: int,
        search_params: Optional[Dict[str, str]] = None,
    ) -> List[Dict]:
        """Run query through GoogleSearch and return metadata.

        Args:
            query: The query to search for.
            num_results: The number of results to return.
            search_params: Parameters to be passed on search

        Returns:
            A list of dictionaries with the following keys:
                snippet - The description of the result.
                title - The title of the result.
                link - The link to the result.
        """
        metadata_results = []
        results = self._google_search_results(
            query, num=num_results, **(search_params or {})
        )
        if len(results) == 0:
            return [{"Result": "No good Google Search Result was found"}]
        for result in results:
            metadata_result = {
                "title": result["title"],
                "link": result["link"],
            }
            if "snippet" in result:
                metadata_result["snippet"] = result["snippet"]
            metadata_results.append(metadata_result)

        return metadata_results


class GoogleSearchRun(BaseTool):
    """Tool that queries the Google search API."""

    name: str = "google_search"
    description: str = (
        "A wrapper around Google Search. "
        "Useful for when you need to answer questions about current events. "
        "Input should be a search query."
    )
    api_wrapper: GoogleSearchAPIWrapper

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return self.api_wrapper.run(query)


class GoogleSearchResults(BaseTool):
    """Tool that queries the Google Search API and gets back json."""

    name: str = "google_search_results_json"
    description: str = (
        "A wrapper around Google Search. "
        "Useful for when you need to answer questions about current events. "
        "Input should be a search query. Output is a JSON array of the query results"
    )
    num_results: int = 4
    api_wrapper: GoogleSearchAPIWrapper

    def _run(
        self,
        query: str,
        run_manager: Optional[CallbackManagerForToolRun] = None,
    ) -> str:
        """Use the tool."""
        return str(self.api_wrapper.results(query, self.num_results))
