import json
import re

raw_data = """Canada
Final squad announced May 29

Goalkeepers: Dayne St. Clair (Inter Miami), Maxime Crépeau (Orlando City), Owen Goodman (Barnsley)

Defenders: Moïse Bombito (Nice), Derek Cornelius (Rangers), Alphonso Davies (Bayern Munich), Luc De Fougerolles (FCV Dender), Alistair Johnston (Celtic), Alfie Jones (Middlesbrough), Richie Laryea (Toronto FC), Niko Sigur (Hajduk Split), Joel Waterman (Chicago Fire)

Midfielders: Ali Ahmed (Norwich City), Tajon Buchanan (Villarreal), Mathieu Choinière (LAFC), Stephen Eustáquio (LAFC), Marcelo Flores (Tigres UANL), Ismaël Koné (Sassuolo), Liam Millar (Hull City), Jonathan Osorio (Toronto FC), Nathan Saliba (Anderlecht), Jacob Shaffelburg (LAFC)

Forwards: Jonathan David (Juventus), Promise David (Royale-Union Saint Gilloise), Cyle Larin (Southampton), Tani Oluwaseyi (Villarreal)
Switzerland
Roster announced May 19

Goalkeepers: Gregor Kobel (Borussia Dortmund), Yvon Mvogo (Lorient), Marvin Keller (Young Boys)

Defenders: Manuel Akanji (Inter Milan), Nico Elvedi (Borussia Mönchengladbach), Ricardo Rodriguez (Real Betis), Silvan Widmer (Mainz), Miro Muheim (Hamburger SV), Aurèle Amenda (Eintracht Frankfurt), Eray Cömert (Valencia), Luca Jaquez (Stuttgart)

Midfielders: Granit Xhaka (Sunderland), Johan Manzambi (Freiburg), Remo Freuler (Bologna), Denis Zakaria (Monaco), Ardon Jashari (AC Milan), Djibril Sow (Sevilla), Christian Fassnacht (Young Boys), Michel Aebischer (Pisa), Fabian Rieder (Augsburg), Rubén Vargas (Sevilla)

Forwards: Breel Embolo (Rennes), Noah Okafor (Leeds), Dan Ndoye (Nottingham Forest), Zeki Amdouni (Burnley), Cedric Itten (Fortuna Dusseldorf)

Scotland
Final squad was announced May 19

Goalkeepers: Craig Gordon (Hearts), Angus Gunn (Nottingham Forest), Liam Kelly (Rangers)

Defenders: Grant Hanley (Hibernian), Jack Hendry (Al Etiffaq), Aaron Hickey (Brentford), Dom Hyam (Wrexham), Scott McKenna (Dinamo Zagreb), Nathan Patterson (Everton), Anthony Ralston (Celtic), Andy Robertson (Liverpool), John Souttar (Rangers), Kieran Tierney (Celtic)

Midfielders: Ryan Christie (Bournemouth), Finlay Curtis (Kilmarnock), Lewis Ferguson (Bologna), Ben Gannon-Doak (Bournemouth), Billy Gilmour (Napoli), John McGinn (Aston Villa), Kenny McLean (Norwich), Scott McTominay (Napoli)

Forwards: Ché Adams (Torino), Lyndon Dykes (Charlton Athletic), George Hirst (Ipswich), Lawrence Shankland (Hearts), Ross Stewart (Southampton)

Australia
Final squad was named on May 31.

Goalkeepers: Mathew Ryan (Levante), Paul Izzo (Randers FC), Patrick Beach (Melbourne City)

Defenders: Jordan Bos (Feyenoord Rotterdam), Aziz Behich (Melbourne City), Harry Souttar (Leicester City), Alessandro Circati (Parma), Lucas Herrington (Colorado Rapids), Cameron Burgess (Swansea City), Kai Trewin (New York City FC), Milos Degenek (Apoel Nicosia), Jason Geria (Albirex Niigata), Jacob Italiano (Grazer AK)

Midfielders: Jackson Irvine (St. Pauli), Aiden O'Neill (New York City FC), Paul Okon Jr (Sydney FC), Cameron Devlin (Heart of Midlothian)

Forwards: Connor Metcalfe (St. Pauli), Mathew Leckie (Melbourne City), Nishan Velupillay (Melbourne Victory), Cristian Volpato (Sassuolo), Nestory Irankunda (Watford), Awer Mabil (Castellón), Ajdin Hrustic (Heracles Almelo), Mohamed Toure (Norwich City), Tete Yengi (Machida Zelvia)

Germany
Roster announced on May 21

Goalkeepers: Oliver Baumann (Hoffenheim), Manuel Neuer (Bayern Munich), Alexander Nübel (Stuttgart)

Defenders: Waldemar Anton (Borussia Dortmund), Nathaniel Brown (Eintracht Frankfurt), David Raum (RB Leipzig), Antonio Rüdiger (Real Madrid), Nico Schlotterbeck (Borussia Dortmund), Jonathan Tah (Bayern Munich), Malick Thiaw (Newcastle)

Midfielders: Pascal Gross (Brighton), Joshua Kimmich (Bayern Munich), Felix Nmecha (Borussia Dortmund), Aleksandar Pavlovic (Bayern Munich), Angelo Stiller (Stuttgart), Leon Goretzka (Bayern Munich), Florian Wirtz (Liverpool), Jamie Leweling (Stuttgart)

Forwards: Maximilian Beier (Borussia Dortmund), Kai Havertz (Arsenal), Lennart Karl (Bayern Munich), Jamal Musiala (Bayern Munich), Leroy Sané (Galatasaray), Deniz Undav (Stuttgart), Nick Woltemade (Newcastle)

Netherlands
Roster announced on May 27.

Goalkeepers: Mark Flekken (Bayer Leverkusen), Robin Roefs (Sunderland), Bart Verbruggen (Brighton)

Defenders: Nathan Aké (Manchester City), Denzel Dumfries (Inter Milan), Jorrel Hato (Chelsea), Jurriën Timber (Arsenal), Jan Paul van Hecke (Brighton), Micky van de Ven (Tottenham), Virgil van Dijk (Liverpool)

Midfielders: Frenkie de Jong (Barcelona), Marten de Roon (Atalanta), Ryan Gravenberch (Liverpool), Teun Koopmeiners (Juventus), Tijjani Reijnders (Manchester City), Guus Til (PSV), Quinten Timber (Marseille), Mats Wieffer (Brighton)

Forwards: Brian Brobbey (Sunderland), Memphis Depay (Corinthians), Cody Gakpo (Liverpool), Justin Kluivert (Bournemouth), Noa Lang (Galatasaray), Donyell Malen (Roma), Crysencio Summerville (West Ham), Wout Weghorst (Ajax)

France
Final squad was announced May 14

Goalkeepers: Mike Maignan (AC Milan), Robin Risser (Lens), Brice Samba (Rennes)

Defenders: Lucas Digne (Aston Villa), Malo Gusto (Chelsea), Lucas Hernández (Paris Saint-Germain), Theo Hernández (Al Hilal), Ibrahima Konaté (Liverpool), Jules Koundé (Barcelona), Maxence Lacroix (Crystal Palace), William Saliba (Arsenal), Dayot Upamecano (Bayern Munich)

Midfielders: N'Golo Kanté (Fenerbahçe), Manu Koné (AS Roma), Adrien Rabiot (AC Milan), Aurélien Tchouaméni (Real Madrid), Warren Zaïre-Emery (Paris Saint-Germain)

Forwards: Maghnes Akliouche (AS Monaco), Bradley Barcola (Paris Saint-Germain), Rayan Cherki (Manchester City), Ousmane Dembélé (Paris Saint-Germain), Désiré Doué (Paris Saint-Germain), Jean-Philippe Mateta (Crystal Palace), Kylian Mbappé (Real Madrid), Michael Olise (Bayern Munich), Marcus Thuram (Internazionale)

England
Roster announced on May 22

Goalkeepers: Jordan Pickford (Everton), Dean Henderson (Crystal Palace), James Trafford (Manchester City)

Defenders: Reece James (Chelsea), Ezri Konsa (Aston Villa), Jarell Quansah (Bayer Leverkusen), John Stones (Manchester City), Marc Guéhi (Manchester City), Dan Burn (Newcastle United), Nico O'Reilly (Manchester City), Djed Spence (Tottenham Hotspur), Tino Livramento (Newcastle United)

Midfielders: Declan Rice (Arsenal), Elliot Anderson (Nottingham Forest), Kobbie Mainoo (Manchester United), Jordan Henderson (Brentford), Morgan Rogers (Aston Villa), Jude Bellingham (Real Madrid), Eberechi Eze (Arsenal)

Forwards: Harry Kane (Bayern Munich), Ivan Toney (Al-Ahli), Ollie Watkins (Aston Villa), Bukayo Saka (Arsenal), Marcus Rashford (Manchester United), Anthony Gordon (Newcastle United), Noni Madueke (Arsenal)
"""

squads = {}
current_country = None

# List of valid positions to check against
VALID_POSITIONS = {'Goalkeepers', 'Defenders', 'Midfielders', 'Forwards'}

lines = raw_data.strip().split('\n')
for line in lines:
    line = line.strip()
    if not line:
        continue
    
    # If the line contains a colon, it's a squad position line
    if ':' in line:
        prefix, rest = line.split(':', 1)
        prefix = prefix.strip()
        
        if prefix in VALID_POSITIONS and current_country:
            players_raw = rest.split(',')
            for p in players_raw:
                # Regex to clean up the name and strip everything from '(' onwards
                clean_p = re.sub(r'\(.*?\)', '', p).strip()
                if clean_p:
                    parts = clean_p.split()
                    aliases = []
                    if len(parts) > 1:
                        aliases.append(parts[-1]) # Last name
                    
                    squads[current_country].append({
                        "name": clean_p,
                        "aliases": aliases
                    })
    else:
        # If it doesn't have a colon and isn't a date/announcement line, it's a country!
        # Explicitly ignore common announcement keywords
        if not any(keyword in line.lower() for keyword in ['announced', 'named', 'manager', 'squad']):
            current_country = line.lower()
            squads[current_country] = []

# Write to file
with open('config/squads.json', 'w', encoding='utf-8') as f:
    json.dump(squads, f, indent=2, ensure_ascii=False)

print("Generated squads.json successfully!")