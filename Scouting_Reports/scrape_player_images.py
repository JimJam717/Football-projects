import requests
from bs4 import BeautifulSoup
import json, time

TEAM_URLS = {
    "Chennai Super Kings":         "https://www.iplt20.com/teams/chennai-super-kings/squad/2025#list",
    "Delhi Capitals":              "https://www.iplt20.com/teams/delhi-capitals/squad/2025#list",
    "Gujarat Titans":              "https://www.iplt20.com/teams/gujarat-titans/squad/2025#list",
    "Kolkata Knight Riders":       "https://www.iplt20.com/teams/kolkata-knight-riders/squad/2025#list",
    "Lucknow Super Giants":        "https://www.iplt20.com/teams/lucknow-super-giants/squad/2025#list",
    "Mumbai Indians":              "https://www.iplt20.com/teams/mumbai-indians/squad/2025#list",
    "Punjab Kings":                "https://www.iplt20.com/teams/punjab-kings/squad/2025#list",
    "Rajasthan Royals":            "https://www.iplt20.com/teams/rajasthan-royals/squad/2025#list",
    "Royal Challengers Bengaluru": "https://www.iplt20.com/teams/royal-challengers-bengaluru/squad/2025#list",
    "Sunrisers Hyderabad":         "https://www.iplt20.com/teams/sunrisers-hyderabad/squad/2025#list"
}

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def discover_selectors():
    team_name = "Chennai Super Kings"
    url = TEAM_URLS[team_name]
    
    print(f"Fetching {team_name} from: {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    try:
        resp = requests.get(url, headers=headers)
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        scripts = soup.find_all('script')
        
        print(f"\nFound {len(scripts)} script tags.")
        
        for i, script in enumerate(scripts):
            content = script.string if script.string else ""
            if len(content) > 1000:
                print(f"\n--- SCRIPT {i} (Length: {len(content)}) ---")
                print(content[:500] + "...")
                # Look for common data keys
                if "player" in content.lower() or "squad" in content.lower():
                    print("  [POTENTIAL PLAYER DATA DETECTED]")
            
            src = script.get('src')
            if src:
                print(f"External Script {i}: {src}")

        # Also print raw HTML near the #root or squad sections
        body = soup.find('body')
        if body:
            print("\n--- BODY PREVIEW ---")
            print(body.get_text()[:1000])

    except Exception as e:
        print(f"Error fetching page: {e}")

if __name__ == '__main__':
    discover_selectors()
