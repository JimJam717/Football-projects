import os
import json
import re
import ast
import time
import unicodedata
import pandas as pd
import numpy as np
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderUnavailable

# Data file paths
DATASET_DIR = r"C:\Users\Pratham\.cache\kagglehub\datasets\piterfm\paris-2024-olympic-summer-games\versions\27"
ATHLETES_CSV = os.path.join(DATASET_DIR, "athletes.csv")
MEDALLISTS_CSV = os.path.join(DATASET_DIR, "medallists.csv")
MEDALS_TOTAL_CSV = os.path.join(DATASET_DIR, "medals_total.csv")
NOCS_CSV = os.path.join(DATASET_DIR, "nocs.csv")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "data")
CACHE_FILE = os.path.join(OUTPUT_DIR, "city_coords_cache.json")
GAMES_OPENING_DATE = pd.Timestamp("2024-07-26")
EXPECTED_DIASPORA_COUNT = 975
INFERRED_NATIVE_BIRTHPLACE_NOCS = {"BRN"}

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------------------------------------------------
# Item 3: NOC vs Sovereign Country Edge Case Mapping Engine
# ---------------------------------------------------------
GBR_CONSTITUENTS = {
    "great britain", "england", "scotland", "wales", "northern ireland",
    "jersey", "guernsey", "isle of man", "gibraltar", "bermuda",
    "cayman islands", "virgin islands, b", "anguilla", "falkland islands",
    "montserrat", "turks and caicos islands"
}

FRA_TERRITORIES = {
    "france", "guadeloupe", "martinique", "french guiana", "runion", "reunion",
    "mayotte", "french polynesia", "new caledonia", "saint martin",
    "saint barthlemy", "saint barthelemy", "saint pierre and miquelon",
    "wallis and futuna"
}

NED_TERRITORIES = {
    "netherlands", "aruba", "curaao", "curacao", "sint maarten", "netherlands antilles"
}

DEN_TERRITORIES = {
    "denmark", "faroe islands", "greenland"
}

USA_TERRITORIES = {
    "united states", "puerto rico", "guam", "virgin islands, us", "american samoa", "northern mariana islands"
}

CHN_ENTITIES = {
    "china", "hong kong, china", "chinese taipei", "taiwan"
}

COUNTRY_NAME_CANONICAL = {
    "russian federation": "Russian Federation",
    "russia": "Russian Federation",
    "united states": "United States",
    "usa": "United States",
    "united states of america": "United States",
    "great britain": "Great Britain",
    "uk": "Great Britain",
    "united kingdom": "Great Britain",
    "cte d'ivoire": "Cte d'Ivoire",
    "cote d'ivoire": "Cte d'Ivoire",
    "trkiye": "Trkiye",
    "turkey": "Trkiye",
    "curaao": "Curaao",
    "curacao": "Curaao",
    "czechia": "Czechia",
    "czechoslovakia": "Czechia",
    "korea": "South Korea",
    "republic of korea": "South Korea",
    "dpr korea": "North Korea",
    "ir iran": "Iran",
    "iran": "Iran",
    "lao pdr": "Laos",
    "republic of moldova": "Moldova",
    "moldova": "Moldova",
    "ua emirates": "United Arab Emirates",
    "united arab emirates": "United Arab Emirates",
    "syria": "Syrian Arab Republic",
    "syrian arab republic": "Syrian Arab Republic",
    "hong kong, china": "Hong Kong",
    "hong kong": "Hong Kong",
    "chinese taipei": "Chinese Taipei",
    "taiwan": "Chinese Taipei",
    "centr afric rep": "Central African Republic",
    "dr congo": "DR Congo",
    "congo": "Congo",
    "stvincent&grenadines": "Saint Vincent and the Grenadines",
    "sao tome & principe": "Sao Tome and Principe",
    "bosnia & herzegovina": "Bosnia and Herzegovina",
}

# NOC Centroid Coordinates
COUNTRY_CENTROIDS = {
    "AFG": [33.9391, 67.7099], "AIN": [55.7558, 37.6173], "ALB": [41.1533, 20.1683], "ALG": [28.0339, 1.6596],
    "AND": [42.5063, 1.5218], "ANG": [-11.2027, 17.8739], "ANT": [17.0608, -61.7964], "ARG": [-38.4161, -63.6167],
    "ARM": [40.0691, 45.0382], "ARU": [12.5211, -69.9683], "ASA": [-14.2710, -170.1322], "AUS": [-25.2744, 133.7751],
    "AUT": [47.5162, 14.5501], "AZE": [40.1431, 47.5769], "BAH": [25.0343, -77.3963], "BAN": [23.6850, 90.3563],
    "BAR": [13.1939, -59.5432], "BDI": [-3.3731, 29.9189], "BEL": [50.5039, 4.4699], "BEN": [9.3077, 2.3158],
    "BER": [32.3078, -64.7505], "BHU": [27.5142, 90.4336], "BIH": [43.9159, 17.6791], "BIZ": [17.1899, -88.4976],
    "BOL": [-16.2902, -63.5887], "BOT": [-22.3285, 24.6849], "BRA": [-14.2350, -51.9253], "BRN": [26.0667, 50.5577],
    "BRU": [4.5353, 114.7277], "BUL": [42.7339, 25.4858], "BUR": [12.2383, -1.5616], "CAF": [6.6111, 20.9394],
    "CAM": [12.5657, 104.9910], "CAN": [56.1304, -106.3468], "CAY": [19.3133, -81.2546], "CGO": [-0.2280, 15.8277],
    "CHA": [15.4542, 18.7322], "CHI": [-35.6751, -71.5430], "CHN": [35.8617, 104.1954], "CIV": [7.5400, -5.5471],
    "CMR": [7.3697, 12.3547], "COD": [-4.0383, 21.7587], "COK": [-21.2367, -159.7777], "COL": [4.5709, -74.2973],
    "COM": [-11.8750, 43.8722], "CPV": [16.0022, -24.0131], "CRC": [9.7489, -83.7534], "CRO": [45.1000, 15.2000],
    "CUB": [21.5218, -77.7812], "CYP": [35.1264, 33.4299], "CZE": [49.8175, 15.4730], "DEN": [56.2639, 9.5018],
    "DJI": [11.8251, 42.5903], "DMA": [15.4150, -61.3710], "DOM": [18.7357, -70.1627], "ECU": [-1.8312, -78.1834],
    "EGY": [26.8206, 30.8025], "EOR": [48.8566, 2.3522], "ERI": [15.1794, 39.7823], "ESA": [13.7942, -88.8965],
    "ESP": [40.4637, -3.7492], "EST": [58.5953, 25.0136], "ETH": [9.1450, 40.4897], "FIJ": [-17.7134, 178.0650],
    "FIN": [61.9241, 25.7482], "FRA": [46.2276, 2.2137], "FSM": [7.4256, 150.5508], "GAB": [-0.8037, 11.6094],
    "GAM": [13.4432, -15.3101], "GBR": [55.3781, -3.4360], "GBS": [11.8037, -15.1804], "GEO": [42.3154, 43.3569],
    "GEQ": [1.6508, 10.2679], "GER": [51.1657, 10.4515], "GHA": [7.9465, -1.0232], "GRE": [39.0742, 21.8243],
    "GRN": [12.1165, -61.6790], "GUA": [15.7835, -90.2308], "GUI": [9.9456, -9.6966], "GUM": [13.4443, 144.7937],
    "GUY": [4.8604, -58.9302], "HAI": [18.9712, -72.2852], "HKG": [22.3193, 114.1694], "HON": [15.2000, -86.2419],
    "HUN": [47.1625, 19.5033], "INA": [-0.7893, 113.9213], "IND": [20.5937, 78.9629], "IRI": [32.4279, 53.6880],
    "IRL": [53.1424, -7.6921], "IRQ": [33.2232, 43.6793], "ISL": [64.9631, -19.0208], "ISR": [31.0461, 34.8516],
    "ISV": [18.3358, -64.8963], "ITA": [41.8719, 12.5674], "IVB": [18.4207, -64.6399], "JAM": [18.1096, -77.2975],
    "JOR": [30.5852, 36.2384], "JPN": [36.2048, 138.2529], "KAZ": [48.0196, 66.9237], "KEN": [-0.0236, 37.9062],
    "KGZ": [41.2044, 74.7661], "KIR": [1.8709, -157.3630], "KOR": [35.9078, 127.7669], "KOS": [42.6026, 20.9030],
    "KSA": [23.8859, 45.0792], "KUW": [29.3117, 47.4818], "LAO": [19.8563, 102.4955], "LAT": [56.8796, 24.6032],
    "LBA": [26.3351, 17.2283], "LBN": [33.8547, 35.8623], "LBR": [6.4281, -9.4295], "LCA": [13.9094, -60.9789],
    "LES": [-29.6099, 28.2336], "LIE": [47.1660, 9.5554], "LTU": [55.1694, 23.8813], "LUX": [49.8153, 6.1296],
    "MAD": [-18.7669, 46.8691], "MAR": [31.7917, -7.0926], "MAS": [4.2105, 101.9758], "MAW": [-13.2543, 34.3015],
    "MDA": [47.4116, 28.3699], "MDV": [3.2028, 73.2207], "MEX": [23.6345, -102.5528], "MGL": [46.8625, 103.8467],
    "MHL": [7.1315, 171.1845], "MKD": [41.6086, 21.7453], "MLI": [17.5707, -3.9962], "MLT": [35.9375, 14.3754],
    "MNE": [42.7087, 19.3744], "MON": [43.7384, 7.4246], "MOZ": [-18.6657, 35.5296], "MRI": [-20.3484, 57.5522],
    "MTN": [21.0079, -10.9408], "MYA": [21.9162, 95.9560], "NAM": [-22.9576, 18.4904], "NCA": [12.8654, -85.2072],
    "NED": [52.1326, 5.2913], "NEP": [28.3949, 84.1240], "NGR": [9.0820, 8.6753], "NIG": [17.6078, 8.0817],
    "NOR": [60.4720, 8.4689], "NRU": [-0.5228, 166.9315], "NZL": [-40.9006, 174.8860], "OMA": [21.4735, 55.9754],
    "PAK": [30.3753, 69.3451], "PAN": [8.5380, -80.7821], "PAR": [-23.4425, -58.4438], "PER": [-9.1900, -75.0152],
    "PHI": [12.8797, 121.7740], "PLE": [31.9522, 35.2332], "PLW": [7.5150, 134.5825], "PNG": [-6.3149, 143.9555],
    "POL": [51.9194, 19.1451], "POR": [39.3999, -8.2245], "PRK": [40.3399, 127.5101], "PUR": [18.2208, -66.5901],
    "QAT": [25.3548, 51.1839], "ROU": [45.9432, 24.9668], "RSA": [-30.5595, 22.9375], "RUS": [61.5240, 105.3188],
    "RWA": [-1.9403, 29.8739], "SAM": [-13.7590, -172.1046], "SEN": [14.4974, -14.4524], "SEY": [-4.6796, 55.4920],
    "SGP": [1.3521, 103.8198], "SKN": [17.3578, -62.7830], "SLE": [8.4606, -11.7799], "SLO": [46.1512, 14.9955],
    "SMR": [43.9424, 12.4578], "SOL": [-9.6457, 160.1562], "SOM": [5.1521, 46.1996], "SRB": [44.0165, 21.0059],
    "SRI": [7.8731, 80.7718], "SSD": [6.8770, 31.3070], "STP": [0.1864, 6.6131], "SUD": [12.8628, 30.2176],
    "SUI": [46.8182, 8.2275], "SUR": [3.9193, -56.0278], "SVK": [48.6690, 19.6990], "SWE": [60.1282, 18.6435],
    "SWZ": [-26.5225, 31.4659], "SYR": [34.8021, 38.9968], "TAN": [-6.3690, 34.8888], "TGA": [-21.1789, -175.1982],
    "THA": [15.8700, 100.9925], "TJK": [38.8610, 71.2761], "TKM": [38.9697, 59.5563], "TLS": [-8.8742, 125.7275],
    "TOG": [8.6195, 0.8248], "TPE": [23.6978, 120.9605], "TTO": [10.6918, -61.2225], "TUN": [33.8869, 9.5375],
    "TUR": [38.9637, 35.2433], "TUV": [-7.1095, 177.6493], "UAE": [23.4241, 53.8478], "UGA": [1.3733, 32.2903],
    "UKR": [48.3794, 31.1656], "URU": [-32.5228, -55.7658], "USA": [37.0902, -95.7129], "UZB": [41.3775, 64.5853],
    "VAN": [-15.3767, 166.9592], "VEN": [6.4238, -66.5897], "VIE": [14.0583, 108.2772], "VIN": [12.9843, -61.2872],
    "YEM": [15.5527, 48.5164], "ZAM": [-13.1339, 27.8493], "ZIM": [-19.0154, 29.1549]
}

COUNTRY_CENTROIDS.update({
    "AIA": [18.2206, -63.0686],
    "BLR": [53.7098, 27.9534],
    "CUR": [12.1696, -68.9900],
    "FRO": [61.8926, -6.9118],
    "MTQ": [14.6415, -61.0242],
    "PYF": [-17.6797, -149.4068],
    "YUG": [44.0165, 21.0059],
})

# Load or init city geocoding cache
city_cache = {}
if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r") as f:
            city_cache = json.load(f)
    except Exception:
        city_cache = {}

# Builtin Static Coordinates for Top 100 Global Olympic Cities
STATIC_CITY_COORDS = {
    "budapest, hungary": [47.4979, 19.0402], "auckland, new zealand": [-36.8485, 174.7633],
    "buenos aires, argentina": [-34.6037, -58.3816], "madrid, spain": [40.4168, -3.7038],
    "berlin, germany": [52.5200, 13.4050], "sydney, nsw, australia": [-33.8688, 151.2093],
    "paris, france": [48.8566, 2.3522], "athens, greece": [37.9838, 23.7275],
    "toronto, on, canada": [43.6532, -79.3832], "rome, italy": [41.9028, 12.4964],
    "rio de janeiro, brazil": [-22.9068, -43.1729], "london, great britain": [51.5074, -0.1278],
    "barcelona, spain": [41.3851, 2.1734], "tokyo, japan": [35.6762, 139.6503],
    "sao paulo, brazil": [-23.5505, -46.6333], "cairo, egypt": [30.0444, 31.2357],
    "montreal, qc, canada": [45.5017, -73.5673], "seoul, korea": [37.5665, 126.9780],
    "melbourne, vic, australia": [-37.8136, 144.9631], "oslo, norway": [59.9139, 10.7522],
    "hamburg, germany": [53.5511, 9.9937], "prague, czechia": [50.0755, 14.4378],
    "belgrade, serbia": [44.7866, 20.4489], "ljubljana, slovenia": [46.0569, 14.5058],
    "dublin, ireland": [53.3498, -6.2603], "tashkent, uzbekistan": [41.2995, 69.2401],
    "kingston, jamaica": [17.9712, -76.7928], "moscow, russian federation": [55.7558, 37.6173],
    "brisbane, qld, australia": [-27.4705, 153.0260], "santiago, chile": [-33.4489, -70.6693],
    "lafayette, la, united states": [30.2241, -92.0198], "le chesnay, france": [48.8252, 2.1328],
    "odense, denmark": [55.4038, 10.4024], "pointe-a-pitre (gua), france": [16.2411, -61.5331],
    "washington, dc, united states": [38.9072, -77.0369], "yaounde, cameroon": [3.8480, 11.5021],
    "columbus, oh, united states": [39.9612, -82.9988], "gainesville, fl, united states": [29.6516, -82.3248],
    "saskatoon, sk, canada": [52.1332, -106.6700], "los angeles, ca, united states": [34.0522, -118.2437],
    "houston, tx, united states": [29.7604, -95.3698], "minsk, belarus": [53.9006, 27.5590],
    "new york, ny, united states": [40.7128, -74.0060], "havana, cuba": [23.1136, -82.3666],
    "belfast, great britain": [54.5973, -5.9301], "munich, germany": [48.1351, 11.5820],
    "lviv, ukraine": [49.8397, 24.0297], "mogadishu, somalia": [2.0469, 45.3182],
    "cape town, south africa": [-33.9249, 18.4241], "chisinau, republic of moldova": [47.0105, 28.8638],
    "hong kong, china": [22.3193, 114.1694]
}

# Merge static into cache
for k, v in STATIC_CITY_COORDS.items():
    city_cache[k] = v

geolocator = Nominatim(user_agent="paris2024_olympic_diaspora_dashboard")


COUNTRY_TO_NOC_MAP = {
    "united states": "USA", "sweden": "SWE", "france": "FRA", "denmark": "DEN",
    "japan": "JPN", "russian federation": "RUS", "russia": "RUS", "kazakhstan": "KAZ",
    "cameroon": "CMR", "serbia": "SRB", "greece": "GRE", "australia": "AUS",
    "canada": "CAN", "germany": "GER", "italy": "ITA", "spain": "ESP",
    "great britain": "GBR", "china": "CHN", "brazil": "BRA", "nigeria": "NGR",
    "puerto rico": "PUR", "jamaica": "JAM", "cuba": "CUB", "kenya": "KEN",
    "ethiopia": "ETH", "morocco": "MAR", "algeria": "ALG", "south africa": "RSA",
    "new zealand": "NZL", "poland": "POL", "netherlands": "NED", "ukraine": "UKR",
    "belgium": "BEL", "switzerland": "SUI", "austria": "AUT", "hungary": "HUN",
    "iran": "IRI", "ir iran": "IRI", "turkey": "TUR", "trkiye": "TUR",
    "mexico": "MEX", "argentina": "ARG", "colombia": "COL", "egypt": "EGY",
    "india": "IND", "south korea": "KOR", "korea": "KOR", "thailand": "THA",
    "cote d'ivoire": "CIV", "cte d'ivoire": "CIV", "dr congo": "COD",
    "republic of moldova": "MDA", "moldova": "MDA", "ua emirates": "UAE",
    "united arab emirates": "UAE", "syria": "SYR", "syrian arab republic": "SYR",
    "hong kong": "HKG", "hong kong, china": "HKG", "chinese taipei": "TPE",
    "taiwan": "TPE", "belarus": "BLR", "yugoslavia": "YUG",
    "netherlands antilles": "CUR", "curaao": "CUR", "curacao": "CUR",
    "faroe islands": "FRO", "anguilla": "AIA", "martinique": "MTQ",
    "french polynesia": "PYF", "german dem. republic": "GER",
}
def normalize_country_name(name):
    if not isinstance(name, str) or not name.strip():
        return None
    cleaned = name.strip().lower()
    return COUNTRY_NAME_CANONICAL.get(cleaned, name.strip())


def normalize_country_key(name):
    if not isinstance(name, str):
        return ""
    normalized_name = normalize_country_name(name)
    if not normalized_name:
        return ""
    normalized = normalized_name.strip().lower()
    return unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")


EX_USSR_COUNTRIES = {
    "armenia", "azerbaijan", "belarus", "estonia", "georgia", "kazakhstan",
    "kyrgyzstan", "latvia", "lithuania", "moldova", "russian federation",
    "russia", "tajikistan", "turkmenistan", "ukraine", "uzbekistan"
}

POST_COLONIAL_PAIRS = set()
for target in [
    "Mali", "Guinea", "Algeria", "Morocco", "Senegal", "Tunisia", "Cameroon",
    "Comoros", "Djibouti", "Mauritania", "Gabon", "Niger", "Benin",
    "Cte d'Ivoire", "Madagascar", "Haiti", "Togo", "Central African Republic",
    "Congo", "DR Congo"
]:
    POST_COLONIAL_PAIRS.add(("france", normalize_country_key(target)))
for target in [
    "Ireland", "Nigeria", "Kenya", "Jamaica", "India", "Pakistan", "Australia",
    "New Zealand", "Canada", "South Africa", "Ghana", "Uganda", "Trinidad and Tobago",
    "Barbados", "Bahamas", "Bermuda", "Cayman Islands", "Saint Lucia", "Belize",
    "Zimbabwe", "Zambia", "Fiji", "Malaysia", "Singapore"
]:
    POST_COLONIAL_PAIRS.add(("great britain", normalize_country_key(target)))
for target in [
    "Argentina", "Bolivia", "Chile", "Colombia", "Costa Rica", "Cuba",
    "Dominican Republic", "Ecuador", "El Salvador", "Guatemala", "Honduras",
    "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Uruguay",
    "Venezuela"
]:
    POST_COLONIAL_PAIRS.add(("spain", normalize_country_key(target)))
for target in ["Brazil", "Angola", "Mozambique", "Cape Verde", "Sao Tome and Principe"]:
    POST_COLONIAL_PAIRS.add(("portugal", normalize_country_key(target)))
for target in ["Suriname", "Aruba", "Curaao", "Netherlands Antilles"]:
    POST_COLONIAL_PAIRS.add(("netherlands", normalize_country_key(target)))

BORDER_PAIRS = {
    ("united states", "canada"), ("united states", "mexico"),
    ("great britain", "ireland"), ("france", "spain"), ("france", "italy"),
    ("france", "germany"), ("france", "belgium"), ("france", "switzerland"),
    ("spain", "portugal"), ("spain", "morocco"), ("germany", "poland"),
    ("germany", "austria"), ("germany", "switzerland"), ("germany", "netherlands"),
    ("germany", "belgium"), ("austria", "hungary"), ("austria", "switzerland"),
    ("austria", "czechia"), ("austria", "slovakia"), ("austria", "slovenia"),
    ("italy", "switzerland"), ("italy", "slovenia"), ("belgium", "netherlands"),
    ("belgium", "luxembourg"), ("netherlands", "germany"), ("poland", "ukraine"),
    ("poland", "belarus"), ("poland", "czechia"), ("poland", "slovakia"),
    ("czechia", "slovakia"), ("hungary", "romania"), ("hungary", "serbia"),
    ("hungary", "croatia"), ("hungary", "slovakia"), ("serbia", "croatia"),
    ("serbia", "bosnia and herzegovina"), ("serbia", "montenegro"),
    ("serbia", "north macedonia"), ("serbia", "kosovo"), ("croatia", "slovenia"),
    ("romania", "moldova"), ("romania", "ukraine"), ("romania", "bulgaria"),
    ("bulgaria", "greece"), ("bulgaria", "turkey"), ("greece", "turkey"),
    ("russian federation", "belarus"), ("russian federation", "ukraine"),
    ("russian federation", "kazakhstan"), ("russian federation", "georgia"),
    ("belarus", "ukraine"), ("ukraine", "moldova"), ("armenia", "georgia"),
    ("armenia", "azerbaijan"), ("georgia", "azerbaijan"),
    ("kazakhstan", "uzbekistan"), ("kazakhstan", "kyrgyzstan"),
    ("uzbekistan", "kyrgyzstan"), ("uzbekistan", "tajikistan"),
    ("uzbekistan", "turkmenistan"), ("china", "hong kong"),
    ("china", "chinese taipei"), ("china", "kazakhstan"), ("china", "kyrgyzstan"),
    ("china", "india"), ("china", "mongolia"), ("china", "laos"),
    ("india", "pakistan"), ("india", "bangladesh"), ("india", "nepal"),
    ("india", "sri lanka"), ("iran", "iraq"), ("iran", "azerbaijan"),
    ("iran", "turkey"), ("kenya", "uganda"), ("kenya", "ethiopia"),
    ("kenya", "tanzania"), ("ethiopia", "eritrea"), ("ethiopia", "djibouti"),
    ("ethiopia", "somalia"), ("morocco", "algeria"), ("algeria", "tunisia"),
    ("algeria", "mali"), ("senegal", "mali"), ("senegal", "gambia"),
    ("nigeria", "cameroon"), ("nigeria", "benin"), ("cameroon", "chad"),
    ("south africa", "zimbabwe"), ("south africa", "botswana"),
    ("south africa", "namibia"), ("south africa", "lesotho"),
    ("australia", "new zealand"), ("argentina", "chile"), ("argentina", "uruguay"),
    ("argentina", "paraguay"), ("argentina", "bolivia"), ("brazil", "argentina"),
    ("brazil", "uruguay"), ("brazil", "paraguay"), ("brazil", "bolivia"),
    ("brazil", "colombia"), ("colombia", "venezuela"), ("colombia", "ecuador"),
    ("ecuador", "peru"), ("peru", "bolivia")
}
BORDER_PAIRS = {tuple(sorted(pair)) for pair in BORDER_PAIRS}

# Corridors between a sovereign state and its own non-sovereign NOCs (either
# direction). These are heritage/eligibility moves within one citizenship space,
# not international migration, so they get their own type.
INTRA_SOVEREIGN_PAIRS = {
    tuple(sorted(pair)) for pair in {
        ("united states", "puerto rico"),
        ("united states", "guam"),
        ("united states", "american samoa"),
        ("united states", "virgin islands, us"),
        ("great britain", "bermuda"),
        ("great britain", "cayman islands"),
        ("great britain", "virgin islands, b"),
        ("new zealand", "cook islands"),
        ("china", "hong kong"),
        ("china", "hong kong, china"),
        ("netherlands", "aruba"),
        ("denmark", "faroe islands"),
    }
}


def clean_value(value):
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        return value if value else None
    return value


def normalize_optional_country(value):
    cleaned = clean_value(value)
    if cleaned is None:
        return None
    return normalize_country_name(cleaned)


def country_matches_noc(country, place, rep_noc, rep_country):
    if not isinstance(country, str) or not country.strip():
        return False

    b_country_clean = normalize_country_key(country)
    b_place_clean = normalize_country_key(place) if isinstance(place, str) else ""
    rep_noc_clean = rep_noc.strip().upper() if isinstance(rep_noc, str) else ""
    rep_country_clean = normalize_country_key(rep_country)

    if b_country_clean and rep_country_clean and b_country_clean == rep_country_clean:
        return True

    if rep_noc_clean == "GBR":
        return b_country_clean in GBR_CONSTITUENTS or any(t in b_place_clean for t in GBR_CONSTITUENTS)
    if rep_noc_clean == "FRA":
        territories = FRA_TERRITORIES - {"france"}
        return b_country_clean in territories or any(t in b_place_clean for t in territories)
    if rep_noc_clean in ["NED", "ARU", "AHO"]:
        territories = NED_TERRITORIES - {"netherlands"}
        if b_country_clean in territories or any(t in b_place_clean for t in territories):
            return rep_noc_clean == "NED" or (
                rep_noc_clean == "ARU"
                and "aruba" in b_country_clean
            )
    if rep_noc_clean == "DEN":
        territories = DEN_TERRITORIES - {"denmark"}
        return b_country_clean in territories or any(t in b_place_clean for t in territories)
    if rep_noc_clean == "HKG":
        return b_country_clean in CHN_ENTITIES or any(t in b_place_clean for t in CHN_ENTITIES)
    if rep_noc_clean == "TPE":
        return b_country_clean in CHN_ENTITIES or any(t in b_place_clean for t in CHN_ENTITIES)
    if rep_noc_clean == "USA":
        territories = USA_TERRITORIES - {"united states"}
        return b_country_clean in territories or any(t in b_place_clean for t in territories)
    if rep_noc_clean == "PUR":
        return b_country_clean == "puerto rico" or "puerto rico" in b_place_clean

    return False


def countries_equivalent(country_a, country_b):
    a = normalize_country_key(country_a)
    b = normalize_country_key(country_b)
    if not a or not b:
        return False
    if a == b:
        return True
    equivalence_sets = [
        GBR_CONSTITUENTS,
        FRA_TERRITORIES,
        NED_TERRITORIES,
        DEN_TERRITORIES,
        USA_TERRITORIES,
        CHN_ENTITIES,
    ]
    return any(a in group and b in group for group in equivalence_sets)


def coords_equal(a, b):
    try:
        return round(float(a[0]), 4) == round(float(b[0]), 4) and round(float(a[1]), 4) == round(float(b[1]), 4)
    except (TypeError, ValueError, IndexError):
        return False


def get_static_key_country(key):
    return key.rsplit(", ", 1)[-1].strip().lower()


def cached_coords_match_country(country, coords):
    country_key = normalize_country_key(country)
    country_noc = COUNTRY_TO_NOC_MAP.get(country_key)

    try:
        lat, lon = float(coords[0]), float(coords[1])
    except (TypeError, ValueError, IndexError):
        return False

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return False

    if coords_equal(coords, [20.0, 0.0]):
        return False

    for static_key, static_coords in STATIC_CITY_COORDS.items():
        if coords_equal(coords, static_coords):
            static_country_key = normalize_country_key(get_static_key_country(static_key))
            static_full_key = normalize_country_key(static_key)
            return (
                static_country_key == country_key
                or static_full_key == country_key
                or static_full_key.startswith(f"{country_key},")
            )

    matching_centroid_nocs = []
    for noc, centroid in COUNTRY_CENTROIDS.items():
        if coords_equal(coords, centroid):
            matching_centroid_nocs.append(noc)

    if matching_centroid_nocs:
        return not country_noc or country_noc in matching_centroid_nocs

    return True


def is_diaspora_athlete(birth_country, birth_place, rep_noc, rep_country):
    if not isinstance(birth_country, str) or not birth_country.strip():
        rep_noc_clean = rep_noc.strip().upper() if isinstance(rep_noc, str) else ""
        if rep_noc_clean in INFERRED_NATIVE_BIRTHPLACE_NOCS:
            return False, "inferred_native_birthplace"
        return False, "missing_birth_data"

    b_country_clean = normalize_country_key(birth_country)
    b_place_clean = normalize_country_key(birth_place) if isinstance(birth_place, str) else ""
    rep_noc_clean = rep_noc.strip().upper() if isinstance(rep_noc, str) else ""
    norm_b = normalize_country_name(birth_country)
    norm_r = normalize_country_name(rep_country)

    if norm_b and norm_r and norm_b.lower() == norm_r.lower():
        return False, "direct_match"

    if rep_noc_clean == "GBR":
        if b_country_clean in GBR_CONSTITUENTS or any(t in b_place_clean for t in GBR_CONSTITUENTS):
            return False, "gbr_constituent"

    if rep_noc_clean == "FRA":
        territories = FRA_TERRITORIES - {"france"}
        if b_country_clean in territories or any(t in b_place_clean for t in territories):
            return False, "fra_territory"

    if rep_noc_clean in ["NED", "ARU", "AHO"]:
        territories = NED_TERRITORIES - {"netherlands"}
        if b_country_clean in territories or any(t in b_place_clean for t in territories):
            if rep_noc_clean == "NED" or (rep_noc_clean == "ARU" and "aruba" in b_country_clean):
                return False, "ned_kingdom"

    if rep_noc_clean == "DEN":
        territories = DEN_TERRITORIES - {"denmark"}
        if b_country_clean in territories or any(t in b_place_clean for t in territories):
            return False, "den_kingdom"

    if rep_noc_clean == "HKG":
        if b_country_clean in CHN_ENTITIES or any(t in b_place_clean for t in CHN_ENTITIES):
            return False, "hkg_china"

    if rep_noc_clean == "TPE":
        if b_country_clean in CHN_ENTITIES or any(t in b_place_clean for t in CHN_ENTITIES):
            return False, "tpe_china"

    if rep_noc_clean == "USA":
        territories = USA_TERRITORIES - {"united states"}
        if b_country_clean in territories or any(t in b_place_clean for t in territories):
            return False, "usa_territory"
    elif rep_noc_clean == "PUR":
        if b_country_clean == "puerto rico" or "puerto rico" in b_place_clean:
            return False, "pur_native"

    return True, "diaspora"


def get_city_coordinates(city, country):
    """
    Geocodes city using static cache or country centroid fallback instantly.
    """
    key = f"{city.strip().lower()}, {country.strip().lower()}"
    if key in city_cache:
        coords = city_cache[key]
        if cached_coords_match_country(country, coords):
            return coords

    # Fallback to country centroid
    b_country_clean = normalize_country_key(country)
    if b_country_clean in COUNTRY_TO_NOC_MAP:
        target_noc = COUNTRY_TO_NOC_MAP[b_country_clean]
        coords = COUNTRY_CENTROIDS.get(target_noc, [0.0, 0.0])
        city_cache[key] = coords
        return coords

    city_cache[key] = [20.0, 0.0]
    return city_cache[key]


def parse_birth_year_and_age(birth_date):
    if not isinstance(birth_date, str) or not birth_date.strip():
        return None, None
    parsed = pd.to_datetime(birth_date, errors="coerce")
    if pd.isna(parsed):
        return None, None
    age = GAMES_OPENING_DATE.year - parsed.year
    if (GAMES_OPENING_DATE.month, GAMES_OPENING_DATE.day) < (parsed.month, parsed.day):
        age -= 1
    return int(parsed.year), int(age)


def classify_identity_profile(birth_country, birth_place, nationality, nationality_code, rep_noc, rep_country):
    if not birth_country or not nationality or not rep_country:
        return "unknown"

    birth_matches_rep = country_matches_noc(birth_country, birth_place, rep_noc, rep_country)
    nat_matches_rep = (
        isinstance(nationality_code, str)
        and isinstance(rep_noc, str)
        and nationality_code.strip().upper() == rep_noc.strip().upper()
    ) or country_matches_noc(nationality, "", rep_noc, rep_country)
    birth_matches_nat = countries_equivalent(birth_country, nationality)

    if birth_matches_rep and nat_matches_rep:
        return "aligned"
    if not birth_matches_rep and nat_matches_rep:
        return "naturalized"
    if not birth_matches_rep and not nat_matches_rep and not birth_matches_nat:
        return "triple_mismatch"
    if not nat_matches_rep:
        return "passport_only"
    return "unknown"


def load_medals_by_athlete():
    if not os.path.exists(MEDALLISTS_CSV):
        return {}, {"medal_rows": 0, "distinct_medalists": 0, "medals_total_sum": None}

    medallists_df = pd.read_csv(MEDALLISTS_CSV)
    if "is_medallist" in medallists_df.columns:
        medallists_df = medallists_df[medallists_df["is_medallist"].fillna(False).astype(bool)]

    seen = set()
    medals_by_athlete = {}
    for _, row in medallists_df.iterrows():
        code = clean_value(row.get("code_athlete"))
        if code is None:
            continue
        try:
            code_key = int(code)
        except (TypeError, ValueError):
            code_key = str(code)
        medal = {
            "medal_type": clean_value(row.get("medal_type")),
            "event": clean_value(row.get("event")),
            "discipline": clean_value(row.get("discipline")),
        }
        dedupe_key = (code_key, medal["medal_type"], medal["event"], medal["discipline"])
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        medals_by_athlete.setdefault(code_key, []).append(medal)

    medals_total_sum = None
    if os.path.exists(MEDALS_TOTAL_CSV):
        totals_df = pd.read_csv(MEDALS_TOTAL_CSV)
        if "Total" in totals_df.columns:
            medals_total_sum = int(totals_df["Total"].fillna(0).sum())
        elif "total" in totals_df.columns:
            medals_total_sum = int(totals_df["total"].fillna(0).sum())

    return medals_by_athlete, {
        "medal_rows": int(len(seen)),
        "distinct_medalists": int(len(medals_by_athlete)),
        "medals_total_sum": medals_total_sum,
    }


def classify_corridor_type(birth_country, rep_country, rep_noc, corridor_count, known_by_country, known_by_rep):
    birth_key = normalize_country_key(birth_country)
    rep_key = normalize_country_key(rep_country)
    rep_noc_clean = rep_noc.strip().upper() if isinstance(rep_noc, str) else ""

    if rep_noc_clean in {"EOR", "AIN"}:
        return "refugee-or-neutral"
    if birth_key in EX_USSR_COUNTRIES and rep_key in EX_USSR_COUNTRIES:
        return "post-soviet"
    if (birth_key, rep_key) in POST_COLONIAL_PAIRS:
        return "post-colonial"
    if tuple(sorted((birth_key, rep_key))) in INTRA_SOVEREIGN_PAIRS:
        return "intra-sovereign"
    if tuple(sorted((birth_key, rep_key))) in BORDER_PAIRS:
        return "neighbor"
    if known_by_country.get(birth_key, 0) >= 100 and known_by_rep.get(rep_key, 0) < 30:
        return "heritage-return"
    if corridor_count >= 3:
        return "talent-market"
    return "unclassified"


def medalist_share(df):
    medalists = df[df["medal_count"] > 0]
    if len(medalists) == 0:
        return 0.0, 0
    diaspora_medalists = medalists[medalists["is_diaspora"]]
    return round(len(diaspora_medalists) / len(medalists) * 100, 2), int(len(medalists))


def run_pipeline():
    print("==========================================================================")
    print("PARIS 2024 OLYMPICS — CITY & COUNTRY LEVEL PIPELINE EXECUTION")
    print("==========================================================================")

    athletes_df = pd.read_csv(ATHLETES_CSV)
    total_athletes = len(athletes_df)
    medals_by_athlete, medal_reconciliation = load_medals_by_athlete()
    known_by_rep_country = (
        athletes_df[athletes_df["birth_country"].notna()]
        .groupby("country")["code"]
        .count()
        .to_dict()
    )
    known_by_rep = {normalize_country_key(country): int(count) for country, count in known_by_rep_country.items()}

    for _, row in athletes_df[["country", "country_code"]].dropna().drop_duplicates().iterrows():
        country_key = normalize_country_key(row["country"])
        noc = str(row["country_code"]).strip().upper()
        if country_key and noc in COUNTRY_CENTROIDS:
            COUNTRY_TO_NOC_MAP[country_key] = noc

    processed_athletes = []
    city_groups = {}

    for idx, row in athletes_df.iterrows():
        b_country = row['birth_country']
        b_place = row['birth_place']
        rep_noc = row['country_code']
        rep_country = row['country']
        name = row['name']
        d_str = str(row['disciplines'])
        m = re.search(r"['\"](.*?)['\"]", d_str)
        sport = m.group(1) if m else d_str.replace('[', '').replace(']', '').replace("'", '').strip()
        nationality = normalize_optional_country(row.get("nationality"))
        nationality_code = clean_value(row.get("nationality_code"))
        residence_place = clean_value(row.get("residence_place"))
        residence_country = normalize_optional_country(row.get("residence_country"))
        birth_year, age_at_games = parse_birth_year_and_age(row.get("birth_date"))
        try:
            code_key = int(row["code"])
        except (TypeError, ValueError):
            code_key = row["code"]
        medals = medals_by_athlete.get(code_key, [])

        is_diaspora, reason = is_diaspora_athlete(b_country, b_place, rep_noc, rep_country)
        if reason == "inferred_native_birthplace":
            birthplace_classification = "inferred_homegrown"
        elif reason == "missing_birth_data":
            birthplace_classification = "unresolved"
        elif is_diaspora:
            birthplace_classification = "recorded_foreign_born"
        else:
            birthplace_classification = "recorded_homegrown"
        trains_abroad = bool(
            residence_country
            and not country_matches_noc(residence_country, "", rep_noc, rep_country)
        )
        residence_status = (
            "unknown"
            if not residence_country
            else "abroad"
            if trains_abroad
            else "home"
        )

        athlete_rec = {
            "code": row['code'],
            "name": name,
            "gender": row['gender'],
            "rep_noc": rep_noc,
            "rep_country": rep_country,
            "nationality": nationality,
            "nationality_code": nationality_code,
            "birth_place": b_place if pd.notna(b_place) else None,
            "birth_country": b_country if pd.notna(b_country) else None,
            "birthplace_classification": birthplace_classification,
            "residence_place": residence_place,
            "residence_country": residence_country,
            "residence_status": residence_status,
            "trains_abroad": trains_abroad,
            "birth_year": birth_year,
            "age_at_games": age_at_games,
            "sport": sport,
            "is_diaspora": is_diaspora,
            "diaspora_reason": reason,
            "identity_profile": classify_identity_profile(
                clean_value(b_country),
                clean_value(b_place),
                nationality,
                nationality_code,
                rep_noc,
                rep_country,
            ),
            "diaspora_type": None,
            "medals": medals,
            "medal_count": len(medals)
        }
        processed_athletes.append(athlete_rec)

        # Aggregate City Level Stats if birth_place and birth_country exist
        if pd.notna(b_place) and pd.notna(b_country):
            city_key = f"{str(b_place).strip().upper()} | {str(b_country).strip()}"
            if city_key not in city_groups:
                city_groups[city_key] = {
                    "city": str(b_place).strip().title(),
                    "birth_country": str(b_country).strip(),
                    "athletes": []
                }
            city_groups[city_key]["athletes"].append(athlete_rec)

    proc_df = pd.DataFrame(processed_athletes)
    diaspora_total = int(proc_df["is_diaspora"].sum())
    if diaspora_total != EXPECTED_DIASPORA_COUNT:
        raise AssertionError(f"Diaspora count changed: expected {EXPECTED_DIASPORA_COUNT}, got {diaspora_total}")

    diaspora_df = proc_df[(proc_df['is_diaspora']) & (proc_df['diaspora_reason'] != "missing_birth_data")]
    corridor_counts = diaspora_df.groupby(["birth_country", "rep_country"]).size().to_dict()
    corridor_types = {}
    for (birth_country, rep_country), count in corridor_counts.items():
        rep_rows = diaspora_df[(diaspora_df["birth_country"] == birth_country) & (diaspora_df["rep_country"] == rep_country)]
        rep_noc = rep_rows["rep_noc"].iloc[0] if len(rep_rows) else ""
        corridor_types[(birth_country, rep_country)] = classify_corridor_type(
            birth_country,
            rep_country,
            rep_noc,
            int(count),
            known_by_rep,
            known_by_rep,
        )

    for athlete in processed_athletes:
        if athlete["is_diaspora"]:
            athlete["diaspora_type"] = corridor_types.get(
                (athlete["birth_country"], athlete["rep_country"]),
                "unclassified"
            )
    proc_df = pd.DataFrame(processed_athletes)
    diaspora_df = proc_df[(proc_df['is_diaspora']) & (proc_df['diaspora_reason'] != "missing_birth_data")]

    # Sport Level Aggregation
    sport_stats_list = []
    for sport in proc_df['sport'].unique():
        sport_df = proc_df[proc_df['sport'] == sport]
        total_sport = len(sport_df)
        recorded_sport = sport_df[sport_df['birth_country'].notna()]
        classified_sport = sport_df[
            sport_df['birth_country'].notna()
            | (sport_df['birthplace_classification'] == "inferred_homegrown")
        ]
        diaspora_sport = classified_sport[classified_sport['is_diaspora']]
        homegrown_sport = classified_sport[~classified_sport['is_diaspora']]
        diaspora_pct = (
            len(diaspora_sport) / len(classified_sport) * 100
            if len(classified_sport) > 0
            else 0.0
        )

        top_sources = diaspora_sport['birth_country'].value_counts().head(5).to_dict()
        top_represented = diaspora_sport['rep_country'].value_counts().head(5).to_dict()
        diaspora_medal_pct, medal_winning_athletes = medalist_share(sport_df)

        sport_stats_list.append({
            "sport": sport,
            "total_athletes": total_sport,
            "total_records_with_birthplace_data": len(recorded_sport),
            "total_classified_birthplace_records": len(classified_sport),
            "inferred_homegrown_count": int(
                (sport_df["birthplace_classification"] == "inferred_homegrown").sum()
            ),
            "homegrown_count": len(homegrown_sport),
            "diaspora_count": len(diaspora_sport),
            "diaspora_pct": round(diaspora_pct, 2),
            "medal_count": int(sport_df["medal_count"].sum()),
            "medal_winning_athletes": medal_winning_athletes,
            "diaspora_medal_count": int(diaspora_sport["medal_count"].sum()),
            "diaspora_medal_pct": diaspora_medal_pct,
            "top_source_countries": top_sources,
            "top_represented_countries": top_represented
        })

    sport_stats_list = sorted(sport_stats_list, key=lambda x: x["total_athletes"], reverse=True)

    # Corridor Level Aggregation
    corridor_groups = {}
    for athlete in processed_athletes:
        if not athlete["is_diaspora"] or athlete["diaspora_reason"] == "missing_birth_data":
            continue
        corridor_key = f"{athlete['birth_country']} | {athlete['rep_country']}"
        if corridor_key not in corridor_groups:
            corridor_groups[corridor_key] = {
                "birth_country": athlete['birth_country'],
                "rep_country": athlete['rep_country'],
                "athletes": []
            }
        corridor_groups[corridor_key]["athletes"].append(athlete)

    corridor_stats_list = []
    for corridor_key, data in corridor_groups.items():
        athletes_in_corridor = data["athletes"]
        sport_counts = pd.Series([a["sport"] for a in athletes_in_corridor]).value_counts().to_dict()
        sports = [{"sport": sport, "count": count} for sport, count in sport_counts.items()]
        birth_country = data["birth_country"]
        rep_country = data["rep_country"]
        athlete_count = len(athletes_in_corridor)
        reverse_count = int(corridor_counts.get((rep_country, birth_country), 0))
        asymmetry = None if reverse_count == 0 else round(max(athlete_count, reverse_count) / min(athlete_count, reverse_count), 2)

        corridor_stats_list.append({
            "birth_country": birth_country,
            "rep_country": rep_country,
            "athlete_count": athlete_count,
            "corridor_type": corridor_types.get((birth_country, rep_country), "unclassified"),
            "reverse_count": reverse_count,
            "asymmetry": asymmetry,
            "medal_count": int(sum(a.get("medal_count", 0) for a in athletes_in_corridor)),
            "sports": sports,
            "athletes": athletes_in_corridor
        })

    corridor_stats_list = sorted(corridor_stats_list, key=lambda x: x["athlete_count"], reverse=True)

    # Residence-based training proxy aggregation
    known_residence_athletes = [
        athlete for athlete in processed_athletes if athlete["residence_status"] != "unknown"
    ]
    home_residence_athletes = [
        athlete for athlete in known_residence_athletes if athlete["residence_status"] == "home"
    ]
    abroad_residence_athletes = [
        athlete for athlete in known_residence_athletes if athlete["residence_status"] == "abroad"
    ]

    training_host_stats = []
    host_groups = {}
    for athlete in abroad_residence_athletes:
        host_groups.setdefault(athlete["residence_country"], []).append(athlete)
    for host_country, athletes_in_host in host_groups.items():
        represented_counts = pd.Series(
            [athlete["rep_country"] for athlete in athletes_in_host]
        ).value_counts().to_dict()
        sport_counts = pd.Series(
            [athlete["sport"] for athlete in athletes_in_host]
        ).value_counts().to_dict()
        host_noc = COUNTRY_TO_NOC_MAP.get(normalize_country_key(host_country))
        training_host_stats.append({
            "host_country": host_country,
            "athlete_count": len(athletes_in_host),
            "represented_team_count": len(represented_counts),
            "top_represented_teams": represented_counts,
            "top_sports": sport_counts,
            "coords": COUNTRY_CENTROIDS.get(host_noc) if host_noc else None,
        })
    training_host_stats.sort(key=lambda item: item["athlete_count"], reverse=True)

    training_team_stats = []
    for rep_noc in proc_df["rep_noc"].unique():
        team_athletes = [
            athlete for athlete in processed_athletes if athlete["rep_noc"] == rep_noc
        ]
        known_team = [
            athlete for athlete in team_athletes if athlete["residence_status"] != "unknown"
        ]
        home_team = [
            athlete for athlete in known_team if athlete["residence_status"] == "home"
        ]
        abroad_team = [
            athlete for athlete in known_team if athlete["residence_status"] == "abroad"
        ]
        top_hosts = pd.Series(
            [athlete["residence_country"] for athlete in abroad_team]
        ).value_counts().to_dict()
        training_team_stats.append({
            "noc": rep_noc,
            "country": team_athletes[0]["rep_country"],
            "total_athletes": len(team_athletes),
            "known_residence_count": len(known_team),
            "home_residence_count": len(home_team),
            "abroad_residence_count": len(abroad_team),
            "abroad_residence_pct": round(
                len(abroad_team) / len(known_team) * 100, 2
            ) if known_team else 0.0,
            "top_host_countries": top_hosts,
            "coords": COUNTRY_CENTROIDS.get(rep_noc),
        })
    training_team_stats.sort(
        key=lambda item: (item["abroad_residence_count"], item["known_residence_count"]),
        reverse=True,
    )

    training_corridor_groups = {}
    for athlete in abroad_residence_athletes:
        key = (athlete["rep_country"], athlete["residence_country"])
        training_corridor_groups.setdefault(key, []).append(athlete)

    training_corridors = []
    for (rep_country, residence_country), athletes_in_corridor in training_corridor_groups.items():
        sports = pd.Series(
            [athlete["sport"] for athlete in athletes_in_corridor]
        ).value_counts().to_dict()
        rep_noc = athletes_in_corridor[0]["rep_noc"]
        residence_noc = COUNTRY_TO_NOC_MAP.get(normalize_country_key(residence_country))
        training_corridors.append({
            "rep_country": rep_country,
            "residence_country": residence_country,
            "athlete_count": len(athletes_in_corridor),
            "sports": [
                {"sport": sport, "count": count}
                for sport, count in sports.items()
            ],
            "from_coords": COUNTRY_CENTROIDS.get(rep_noc),
            "to_coords": COUNTRY_CENTROIDS.get(residence_noc) if residence_noc else None,
            "athletes": athletes_in_corridor,
        })
    training_corridors.sort(key=lambda item: item["athlete_count"], reverse=True)

    training_sport_stats = []
    for sport in proc_df["sport"].unique():
        sport_athletes = [
            athlete for athlete in processed_athletes if athlete["sport"] == sport
        ]
        known_sport = [
            athlete for athlete in sport_athletes if athlete["residence_status"] != "unknown"
        ]
        abroad_sport = [
            athlete for athlete in known_sport if athlete["residence_status"] == "abroad"
        ]
        training_sport_stats.append({
            "sport": sport,
            "total_athletes": len(sport_athletes),
            "known_residence_count": len(known_sport),
            "abroad_residence_count": len(abroad_sport),
            "abroad_residence_pct": round(
                len(abroad_sport) / len(known_sport) * 100, 2
            ) if known_sport else 0.0,
        })
    training_sport_stats.sort(
        key=lambda item: item["abroad_residence_count"],
        reverse=True,
    )

    training_stats = {
        "definition": "Residence country is used as a proxy for training location; it does not identify an athlete's actual training base or facility.",
        "summary": {
            "total_athletes": len(processed_athletes),
            "known_residence_count": len(known_residence_athletes),
            "missing_residence_count": len(processed_athletes) - len(known_residence_athletes),
            "home_residence_count": len(home_residence_athletes),
            "abroad_residence_count": len(abroad_residence_athletes),
            "abroad_residence_pct": round(
                len(abroad_residence_athletes) / len(known_residence_athletes) * 100, 2
            ) if known_residence_athletes else 0.0,
        },
        "host_countries": training_host_stats,
        "team_stats": training_team_stats,
        "corridors": training_corridors,
        "sport_stats": training_sport_stats,
    }

    # Compute City Stats
    city_stats_list = []
    print(f"\nProcessing {len(city_groups):,} unique birth city locations...")

    for city_key, data in city_groups.items():
        city_name = data["city"]
        b_country = data["birth_country"]
        athletes_in_city = data["athletes"]

        total_born = len(athletes_in_city)
        diaspora_athletes = [a for a in athletes_in_city if a["is_diaspora"]]
        diaspora_count = len(diaspora_athletes)
        homegrown_count = total_born - diaspora_count
        diaspora_pct = round((diaspora_count / total_born) * 100, 2)

        rep_nocs = list(set(a["rep_noc"] for a in athletes_in_city))
        rep_countries = list(set(a["rep_country"] for a in athletes_in_city))
        sports = list(set(a["sport"] for a in athletes_in_city))

        coords = get_city_coordinates(city_name, b_country)

        city_stats_list.append({
            "id": city_key,
            "city": city_name,
            "birth_country": b_country,
            "coords": coords,
            "total_born": total_born,
            "diaspora_count": diaspora_count,
            "homegrown_count": homegrown_count,
            "diaspora_pct": diaspora_pct,
            "represented_nocs": rep_nocs,
            "represented_countries": rep_countries,
            "sports": sports,
            "diaspora_athletes": diaspora_athletes,
            "all_athletes": athletes_in_city
        })

    # Save Cache
    with open(CACHE_FILE, "w") as f:
        json.dump(city_cache, f, indent=2)

    # Save City Stats
    with open(os.path.join(OUTPUT_DIR, "city_stats.json"), "w") as f:
        json.dump(city_stats_list, f, indent=2)

    # Save Sport Stats
    with open(os.path.join(OUTPUT_DIR, "sport_stats.json"), "w") as f:
        json.dump(sport_stats_list, f, indent=2)

    # Save Corridor Stats
    with open(os.path.join(OUTPUT_DIR, "corridor_stats.json"), "w") as f:
        json.dump(corridor_stats_list, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "training_stats.json"), "w") as f:
        json.dump(training_stats, f, indent=2)

    # Country Level Aggregation
    country_stats = {}
    for noc in proc_df['rep_noc'].unique():
        noc_df = proc_df[proc_df['rep_noc'] == noc]
        total_rep = len(noc_df)
        recorded_rep = noc_df[noc_df['birth_country'].notna()]
        classified_rep = noc_df[
            noc_df['birth_country'].notna()
            | (noc_df['birthplace_classification'] == "inferred_homegrown")
        ]
        foreign_born = classified_rep[classified_rep['is_diaspora']]
        homegrown = classified_rep[~classified_rep['is_diaspora']]
        foreign_pct = (
            len(foreign_born) / len(classified_rep) * 100
            if len(classified_rep) > 0
            else 0.0
        )

        top_sources = foreign_born['birth_country'].value_counts().head(5).to_dict()
        c_name = noc_df['rep_country'].iloc[0]
        coords = COUNTRY_CENTROIDS.get(noc, [0.0, 0.0])
        diaspora_medal_pct, medal_winning_athletes = medalist_share(noc_df)

        country_stats[noc] = {
            "noc": noc,
            "country": c_name,
            "total_athletes": total_rep,
            "total_records_with_birthplace_data": len(recorded_rep),
            "total_classified_birthplace_records": len(classified_rep),
            "inferred_homegrown_count": int(
                (noc_df["birthplace_classification"] == "inferred_homegrown").sum()
            ),
            "homegrown_count": len(homegrown),
            "foreign_born_count": len(foreign_born),
            "foreign_born_pct": round(foreign_pct, 2),
            "medal_count": int(noc_df["medal_count"].sum()),
            "medal_winning_athletes": medal_winning_athletes,
            "diaspora_medal_count": int(foreign_born["medal_count"].sum()),
            "diaspora_medal_pct": diaspora_medal_pct,
            "top_source_countries": top_sources,
            "coords": coords
        }

    medalists_df = proc_df[proc_df["medal_count"] > 0]
    known_df = proc_df[proc_df["birth_country"].notna()]
    diaspora_medalists_df = medalists_df[medalists_df["is_diaspora"]]
    excluded_nocs = {"EOR", "AIN"}
    known_ex_team_df = known_df[~known_df["rep_noc"].isin(excluded_nocs)]
    medalists_ex_team_df = medalists_df[~medalists_df["rep_noc"].isin(excluded_nocs)]
    diaspora_medalists_ex_team_df = medalists_ex_team_df[medalists_ex_team_df["is_diaspora"]]

    diaspora_share_all = round(len(known_df[known_df["is_diaspora"]]) / len(known_df) * 100, 2) if len(known_df) else 0.0
    diaspora_share_medalists = round(len(diaspora_medalists_df) / len(medalists_df) * 100, 2) if len(medalists_df) else 0.0
    diaspora_share_all_ex_team = round(len(known_ex_team_df[known_ex_team_df["is_diaspora"]]) / len(known_ex_team_df) * 100, 2) if len(known_ex_team_df) else 0.0
    diaspora_share_medalists_ex_team = round(len(diaspora_medalists_ex_team_df) / len(medalists_ex_team_df) * 100, 2) if len(medalists_ex_team_df) else 0.0

    summary_stats = {
        "total_athletes": int(total_athletes),
        "known_birthplace_athletes": int(len(known_df)),
        "diaspora_athletes": diaspora_total,
        "diaspora_share_all_athletes": diaspora_share_all,
        "total_medal_winning_athletes": int(len(medalists_df)),
        "diaspora_medal_winning_athletes": int(len(diaspora_medalists_df)),
        "diaspora_share_medal_winners": diaspora_share_medalists,
        "diaspora_medalist_vs_all_delta": round(diaspora_share_medalists - diaspora_share_all, 2),
        "excluding_eor_ain": {
            "known_birthplace_athletes": int(len(known_ex_team_df)),
            "diaspora_athletes": int(known_ex_team_df["is_diaspora"].sum()),
            "diaspora_share_all_athletes": diaspora_share_all_ex_team,
            "total_medal_winning_athletes": int(len(medalists_ex_team_df)),
            "diaspora_medal_winning_athletes": int(len(diaspora_medalists_ex_team_df)),
            "diaspora_share_medal_winners": diaspora_share_medalists_ex_team,
            "diaspora_medalist_vs_all_delta": round(diaspora_share_medalists_ex_team - diaspora_share_all_ex_team, 2),
        },
        "medal_reconciliation": medal_reconciliation,
    }

    with open(os.path.join(OUTPUT_DIR, "olympics_diaspora.json"), "w") as f:
        json.dump(processed_athletes, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "country_stats.json"), "w") as f:
        json.dump(country_stats, f, indent=2)

    with open(os.path.join(OUTPUT_DIR, "summary_stats.json"), "w") as f:
        json.dump(summary_stats, f, indent=2)

    print(f"\nCOMPLETE: City stats exported ({len(city_stats_list):,} cities) to data/city_stats.json")
    print(f"COMPLETE: Sport stats exported ({len(sport_stats_list):,} sports) to data/sport_stats.json")
    print(f"COMPLETE: Corridor stats exported ({len(corridor_stats_list):,} corridors) to data/corridor_stats.json")
    print(f"COMPLETE: Residence proxy stats exported ({len(training_corridors):,} corridors) to data/training_stats.json")
    print("COMPLETE: Summary stats exported to data/summary_stats.json")
    print("\nGLOBAL SUMMARY")
    print(f"Total athletes: {summary_stats['total_athletes']:,}")
    print(f"Known birthplaces: {summary_stats['known_birthplace_athletes']:,}")
    print(f"Diaspora athletes: {summary_stats['diaspora_athletes']:,} ({summary_stats['diaspora_share_all_athletes']}%)")
    print(
        "Medal-winning athletes: "
        f"{summary_stats['total_medal_winning_athletes']:,}; diaspora medalists: "
        f"{summary_stats['diaspora_medal_winning_athletes']:,} "
        f"({summary_stats['diaspora_share_medal_winners']}%, "
        f"delta {summary_stats['diaspora_medalist_vs_all_delta']:+.2f} pts vs all athletes)"
    )
    ex = summary_stats["excluding_eor_ain"]
    print(
        "Excluding EOR/AIN: "
        f"{ex['diaspora_share_medal_winners']}% of medal-winning athletes vs "
        f"{ex['diaspora_share_all_athletes']}% of all known-birthplace athletes "
        f"({ex['diaspora_medalist_vs_all_delta']:+.2f} pts)"
    )
    print(
        "Medal reconciliation: "
        f"{medal_reconciliation['medal_rows']:,} per-athlete medal entries in medallists.csv; "
        f"{medal_reconciliation['distinct_medalists']:,} distinct athlete codes; "
        f"medals_total.csv sum={medal_reconciliation['medals_total_sum']}"
    )
    print("\nTOP 5 CORRIDORS BY ATHLETE COUNT")
    for corridor in corridor_stats_list[:5]:
        print(
            f"{corridor['birth_country']} -> {corridor['rep_country']}: "
            f"{corridor['athlete_count']} ({corridor['corridor_type']}, medals={corridor['medal_count']})"
        )
    print("==========================================================================\n")


if __name__ == "__main__":
    run_pipeline()
