import httpx
import os
import asyncio
from typing import Dict, List, Any, Optional


def get_env_value(*names: str) -> Optional[str]:
    """
    Read the first configured environment variable from a list of accepted names.
    """
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


def safe_value(value: Any, default: str = "N/A") -> str:
    if value is None or value == "":
        return default
    return str(value)


async def fetch_json(client: httpx.AsyncClient, url: str, params: Dict[str, Any]) -> Any:
    try:
        response = await client.get(url, params=params, timeout=20.0)
        if response.status_code != 200:
            return {"error": f"HTTP {response.status_code}", "url": str(response.url), "body": response.text[:300]}
        return response.json()
    except Exception as exc:
        return {"error": str(exc), "url": url}

async def search_tavily(query: str, api_key: str) -> List[Dict[str, Any]]:
    """
    Search Tavily API for a specific query.
    Falls back gracefully if the API key is not configured.
    """
    if not api_key:
        return [{
            "title": f"Mock Result for '{query}'",
            "url": "https://example.com/mock",
            "content": f"This is a mock search result because TAVILY_API_KEY is not set. Query: {query}"
        }]
    
    url = "https://api.tavily.com/search"
    payload = {
        "api_key": api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": 2
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, timeout=15.0)
            if response.status_code == 200:
                data = response.json()
                return data.get("results", [])
            else:
                return [{
                    "title": f"Tavily API Error: {response.status_code}",
                    "url": "https://api.tavily.com",
                    "content": f"Failed to fetch search results from Tavily. API returned status code {response.status_code}."
                }]
    except Exception as e:
        return [{
            "title": "Network Error",
            "url": "https://api.tavily.com",
            "content": f"A network connection error occurred while searching for '{query}': {str(e)}"
        }]


async def resolve_symbol_with_fmp(company: str, api_key: Optional[str]) -> Optional[str]:
    """
    Resolve a company name to a ticker symbol through Financial Modeling Prep.
    """
    if not api_key:
        return None

    async with httpx.AsyncClient() as client:
        data = await fetch_json(
            client,
            "https://financialmodelingprep.com/stable/search-name",
            {"query": company, "limit": 10, "apikey": api_key}
        )

    if isinstance(data, list) and data:
        preferred_exchanges = {"NASDAQ", "NYSE", "AMEX"}
        for item in data:
            if item.get("currency") == "USD" and item.get("exchange") in preferred_exchanges:
                return item.get("symbol")
        for item in data:
            if item.get("currency") == "USD":
                return item.get("symbol")
        return data[0].get("symbol")
    return None


async def get_fmp_company_data(company: str, symbol: Optional[str], api_key: Optional[str]) -> str:
    """
    Fetch profile, quote, income statement, and employee count from Financial Modeling Prep.
    """
    if not api_key:
        return "### Financial Modeling Prep Data\nFMP key not configured.\n"

    symbol = symbol or await resolve_symbol_with_fmp(company, api_key)
    if not symbol:
        return f"### Financial Modeling Prep Data\nCould not resolve a public ticker symbol for {company}.\n"

    async with httpx.AsyncClient() as client:
        profile_task = fetch_json(client, "https://financialmodelingprep.com/stable/profile", {"symbol": symbol, "apikey": api_key})
        quote_task = fetch_json(client, "https://financialmodelingprep.com/stable/quote", {"symbol": symbol, "apikey": api_key})
        income_task = fetch_json(client, "https://financialmodelingprep.com/stable/income-statement", {"symbol": symbol, "limit": 3, "apikey": api_key})
        employees_task = fetch_json(client, "https://financialmodelingprep.com/stable/employee-count", {"symbol": symbol, "apikey": api_key})
        profile, quote, income, employees = await asyncio.gather(profile_task, quote_task, income_task, employees_task)

    errors = [item.get("error") for item in [profile, quote, income, employees] if isinstance(item, dict) and item.get("error")]
    if errors:
        return (
            "### Financial Modeling Prep Data\n"
            f"FMP request failed for symbol {symbol}: {', '.join(errors)}. "
            "Check that the FMP API key is valid and has access to profile, quote, income statement, and employee count endpoints.\n"
        )

    profile_item = profile[0] if isinstance(profile, list) and profile else {}
    quote_item = quote[0] if isinstance(quote, list) and quote else {}
    latest_income = income[0] if isinstance(income, list) and income else {}
    latest_employee = employees[0] if isinstance(employees, list) and employees else {}

    lines = [
        "### Financial Modeling Prep Data",
        f"- **Resolved symbol:** {symbol}",
        f"- **Company name:** {safe_value(profile_item.get('companyName'))}",
        f"- **Industry:** {safe_value(profile_item.get('industry'))}",
        f"- **Sector:** {safe_value(profile_item.get('sector'))}",
        f"- **CEO:** {safe_value(profile_item.get('ceo'))}",
        f"- **Website:** {safe_value(profile_item.get('website'))}",
        f"- **Market cap:** {safe_value(profile_item.get('mktCap') or quote_item.get('marketCap'))}",
        f"- **Price:** {safe_value(quote_item.get('price'))}",
        f"- **Exchange:** {safe_value(profile_item.get('exchangeShortName') or quote_item.get('exchange'))}",
        f"- **Latest reported revenue:** {safe_value(latest_income.get('revenue'))}",
        f"- **Latest reported net income:** {safe_value(latest_income.get('netIncome'))}",
        f"- **Latest income statement date:** {safe_value(latest_income.get('date'))}",
        f"- **Latest employee count:** {safe_value(latest_employee.get('employeeCount'))}",
        f"- **Employee count date:** {safe_value(latest_employee.get('periodOfReport'))}",
        "- **Sources:** Financial Modeling Prep profile, quote, income statement, and employee count endpoints."
    ]

    description = profile_item.get("description")
    if description:
        lines.append(f"- **Business description:** {description[:900]}")

    return "\n".join(lines) + "\n"


async def get_alpha_vantage_data(symbol: Optional[str], api_key: Optional[str]) -> str:
    """
    Fetch compact historical daily stock data from Alpha Vantage.
    """
    if not api_key:
        return "### Alpha Vantage Historical Data\nAlpha Vantage key not configured.\n"
    if not symbol:
        return "### Alpha Vantage Historical Data\nNo ticker symbol available for historical data lookup.\n"

    async with httpx.AsyncClient() as client:
        data = await fetch_json(
            client,
            "https://www.alphavantage.co/query",
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": symbol,
                "outputsize": "compact",
                "apikey": api_key
            }
        )

    if not isinstance(data, dict):
        return "### Alpha Vantage Historical Data\nUnexpected Alpha Vantage response.\n"
    if "Error Message" in data:
        return f"### Alpha Vantage Historical Data\nAlpha Vantage error: {data['Error Message']}\n"
    if "Note" in data:
        return f"### Alpha Vantage Historical Data\nAlpha Vantage note: {data['Note']}\n"

    series = data.get("Time Series (Daily)", {})
    if not series:
        return "### Alpha Vantage Historical Data\nNo daily historical series returned.\n"

    dates = sorted(series.keys(), reverse=True)[:5]
    lines = [
        "### Alpha Vantage Historical Data",
        f"- **Symbol:** {symbol}",
        "- **Recent daily prices:**"
    ]

    for date in dates:
        day = series[date]
        lines.append(
            f"  - {date}: open {safe_value(day.get('1. open'))}, "
            f"high {safe_value(day.get('2. high'))}, low {safe_value(day.get('3. low'))}, "
            f"close {safe_value(day.get('4. close'))}, volume {safe_value(day.get('5. volume'))}"
        )

    lines.append("- **Source:** Alpha Vantage TIME_SERIES_DAILY endpoint.")
    return "\n".join(lines) + "\n"

async def get_company_research(
    company: str,
    api_key: str,
    user_query: str = "",
    validation_notes: str = "",
    attempt: int = 1
) -> str:
    """
    Gather news, financials, and recent developments for a company in parallel.
    """
    refinement = ""
    if validation_notes and attempt > 1:
        refinement = f" missing details: {validation_notes}"

    queries = [
        f"{company} business overview latest news {user_query}{refinement}",
        f"{company} financials revenue valuation stock performance {user_query}{refinement}",
        f"{company} recent developments leadership competitors strategy {user_query}{refinement}"
    ]
    
    # Execute the three searches concurrently
    fmp_key = get_env_value("FINANCIAL_MODELING_PREP_API_KEY", "FMP_API_KEY", "financialmodelingprep")
    alpha_key = get_env_value("ALPHA_VANTAGE_API_KEY", "Alpha_Vantage", "alpha_vantage")
    symbol = await resolve_symbol_with_fmp(company, fmp_key)

    tasks = [search_tavily(q, api_key) for q in queries]
    fmp_task = get_fmp_company_data(company, symbol, fmp_key)
    alpha_task = get_alpha_vantage_data(symbol, alpha_key)
    results, fmp_data, alpha_data = await asyncio.gather(
        asyncio.gather(*tasks),
        fmp_task,
        alpha_task
    )
    
    formatted_findings = []
    formatted_findings.append(fmp_data)
    formatted_findings.append(alpha_data)
    categories = ["News & Recent Media", "Financials & Valuation", "Recent Developments & Operations"]
    
    for category, category_results in zip(categories, results):
        formatted_findings.append(f"### {category}")
        if not category_results:
            formatted_findings.append("No results found.\n")
            continue
            
        for idx, res in enumerate(category_results, 1):
            title = res.get("title", "Untitled Source")
            url = res.get("url", "")
            content = res.get("content", "")
            formatted_findings.append(f"{idx}. **{title}**")
            if url:
                formatted_findings.append(f"   Source: {url}")
            if content:
                formatted_findings.append(f"   Snippet: {content}")
            formatted_findings.append("")
            
    return "\n".join(formatted_findings)
