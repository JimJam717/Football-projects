import json
import re

def extract_mentions(text, squads):
    """
    Given a text string and a squads dict, returns a list of matched player dicts:
    [{"nation": "england", "name": "Bukayo Saka"}, ...]
    """
    matches = []
    text_lower = text.lower()
    
    # Optional optimization: pre-compile regex boundaries if exact word match is needed,
    # but prompt just says "matches on full name or any alias".
    # Using regex with \b word boundaries to avoid matching sub-strings (e.g. "Saka" inside "Osaka")
    
    for nation, players in squads.items():
        for player in players:
            full_name = player['name'].lower()
            aliases = [a.lower() for a in player.get('aliases', [])]
            
            # Check full name
            matched = False
            # We use \b boundary to make sure we don't match substrings
            if re.search(r'\b' + re.escape(full_name) + r'\b', text_lower):
                matched = True
            else:
                for alias in aliases:
                    if re.search(r'\b' + re.escape(alias) + r'\b', text_lower):
                        matched = True
                        break
            
            if matched:
                matches.append({"nation": nation, "name": player['name']})
                
    return matches

if __name__ == "__main__":
    squads = {
        "england": [{"name": "Bukayo Saka", "aliases": ["Saka"]}]
    }
    print(extract_mentions("What a goal by Saka!", squads))
    print(extract_mentions("Bukayo Saka is playing well", squads))
    print(extract_mentions("Osakaplay", squads)) # Should not match
