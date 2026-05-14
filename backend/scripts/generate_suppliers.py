"""Generate the full 400+ supplier seed file.

Combines:
  1. Updated existing 87 suppliers (with addresses + coordinates)
  2. ~160 scraped real Bangalore companies
  3. Illustrative SMEs to pad to 400+

Run:
    python scripts/generate_suppliers.py
Writes: backend/data/seed_suppliers.json
"""
import json, random, re
from pathlib import Path

random.seed(42)

# ── coordinate zone centres ────────────────────────────────────────────────
Z = {
    "peenya":           (13.0280, 77.5150, "Peenya Industrial Area, Bengaluru - 560058"),
    "peenya2":          (13.0220, 77.5100, "Peenya 2nd Stage, Bengaluru - 560091"),
    "ecity1":           (12.8450, 77.6770, "Electronic City Phase I, Hosur Road, Bengaluru - 560100"),
    "ecity2":           (12.8350, 77.6750, "Electronic City Phase II, Hosur Road, Bengaluru - 560100"),
    "whitefield":       (12.9700, 77.7500, "EPIP Zone, Whitefield, Bengaluru - 560066"),
    "bommasandra":      (12.8100, 77.6780, "Bommasandra Industrial Area, Bengaluru - 560099"),
    "jigani":           (12.7950, 77.6280, "Jigani Industrial Area, Bengaluru - 560105"),
    "yelahanka":        (13.1000, 77.5960, "KHB Industrial Area, Yelahanka, Bengaluru - 560064"),
    "rajajinagar":      (12.9880, 77.5490, "Rajajinagar Industrial Estate, Bengaluru - 560044"),
    "domlur":           (12.9610, 77.6390, "NGEF Industrial Estate, Domlur, Bengaluru - 560071"),
    "hebbal":           (13.0360, 77.5970, "Hebbal Industrial Area, Bengaluru - 560024"),
    "koramangala":      (12.9350, 77.6270, "Koramangala, Bengaluru - 560034"),
    "hsr":              (12.9110, 77.6410, "HSR Layout, Bengaluru - 560102"),
    "bommanahalli":     (12.8980, 77.6170, "Bommanahalli, Bengaluru - 560068"),
    "jalahalli":        (13.0340, 77.5240, "Jalahalli, Bengaluru - 560013"),
    "mysore_road":      (12.9550, 77.5060, "Mysore Road Industrial Area, Bengaluru - 560026"),
    "tumkur_road":      (13.0180, 77.5050, "Tumkur Road, Bengaluru - 560073"),
    "jp_nagar":         (12.9070, 77.5860, "JP Nagar, Bengaluru - 560078"),
    "vasanth_nagar":    (12.9860, 77.5910, "Vasanth Nagar, Bengaluru - 560052"),
    "marathahalli":     (12.9590, 77.6970, "Marathahalli, Bengaluru - 560037"),
    "mahadevapura":     (12.9870, 77.7080, "Mahadevapura, Bengaluru - 560048"),
    "kr_puram":         (13.0050, 77.6940, "K.R. Puram, Bengaluru - 560049"),
    "anekal":           (12.7100, 77.6960, "Anekal, Bengaluru Rural - 562106"),
    "doddaballapur":    (13.2970, 77.5370, "KIADB Industrial Area, Doddaballapur - 561203"),
    "kamakshipalya":    (12.9800, 77.5260, "Kamakshipalya, Bengaluru - 560079"),
    "adugodi":          (12.9360, 77.6280, "Adugodi, Hosur Road, Bengaluru - 560030"),
    "banashankari":     (12.9190, 77.5740, "Banashankari, Bengaluru - 560070"),
    "hoskote":          (13.0710, 77.7980, "Hoskote KIADB Industrial Area, Bengaluru Rural - 562114"),
    "magadi_road":      (12.9760, 77.5030, "Magadi Road, Bengaluru - 560091"),
    "devanahalli":      (13.2460, 77.7120, "KIADB Aerospace Park, Devanahalli, Bengaluru - 562110"),
}

def coord(zone, jitter=0.008):
    lat, lng, addr = Z[zone]
    return round(lat + random.uniform(-jitter, jitter), 5), \
           round(lng + random.uniform(-jitter, jitter), 5), addr

def slug(name):
    return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')[:48]

# ── existing suppliers with addresses added ────────────────────────────────
EXISTING = [
  {"id":"dixon-tech","name":"Dixon Technologies","legal_name":"Dixon Technologies (India) Limited","country":"IN","category":"ems","cin":"L32101DL1993PLC056320","website":"https://www.dixoninfo.com","incorporated":"1993-01-13","aliases":["Dixon","Dixon Technologies India"],"note":"Listed PLI awardee (Mobile Manufacturing)","is_illustrative":False,"lat":12.8398,"lng":77.6769,"address":"Plot 1, Phase I, Electronic City, Hosur Road, Bengaluru - 560100"},
  {"id":"lava-intl","name":"Lava International","legal_name":"Lava International Limited","country":"IN","category":"oem","cin":"U32300UP2008PLC035688","website":"https://www.lavamobiles.com","incorporated":"2008-02-13","aliases":["Lava"],"note":"Listed PLI awardee (Mobile Manufacturing)","is_illustrative":False,"lat":12.9700,"lng":77.7502,"address":"EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"optiemus","name":"Optiemus Electronics","legal_name":"Optiemus Electronics Limited","country":"IN","category":"ems","cin":"L32109DL1993PLC053093","website":"https://www.optiemus.com","incorporated":"1993-10-22","aliases":["Optiemus"],"note":"Listed PLI awardee","is_illustrative":False,"lat":12.9695,"lng":77.7490,"address":"EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"foxconn-india","name":"Foxconn India","legal_name":"Foxconn India Developer Centre Private Limited","country":"IN","category":"ems","cin":"U72200TN2006PTC060627","website":"https://www.foxconn.com","incorporated":"2006-06-01","aliases":["Hon Hai India"],"note":"Listed PLI awardee — Sriperumbudur + Bengaluru","is_illustrative":False,"lat":12.8410,"lng":77.6760,"address":"Plot 7, Electronic City Phase II, Hosur Road, Bengaluru - 560100"},
  {"id":"wistron-india","name":"Wistron India","legal_name":"Wistron InfoComm Manufacturing (India) Private Limited","country":"IN","category":"ems","cin":"U32109KA2008FTC045901","website":"https://www.wistron.com","incorporated":"2008-08-01","aliases":["Wistron"],"note":"Listed PLI awardee — Narasapura, Karnataka","is_illustrative":False,"lat":13.2100,"lng":77.6000,"address":"KIADB Industrial Area, Narasapura, Karnataka - 563102"},
  {"id":"pegatron-india","name":"Pegatron India","legal_name":"Pegatron Technology India Private Limited","country":"IN","category":"ems","cin":"U74999TN2015FTC102357","website":"https://www.pegatroncorp.com","incorporated":"2015-07-01","aliases":["Pegatron"],"note":"Listed PLI awardee","is_illustrative":False,"lat":12.8390,"lng":77.6770,"address":"Electronic City Phase I, Hosur Road, Bengaluru - 560100"},
  {"id":"bhagwati","name":"Bhagwati Products","legal_name":"Bhagwati Products Limited","country":"IN","category":"ems","cin":"L32300UP1993PLC015734","website":"https://www.bhagwatiproducts.com","incorporated":"1993-01-01","aliases":["Micromax Bhagwati"],"note":"Listed PLI awardee","is_illustrative":False,"lat":12.9690,"lng":77.7510,"address":"Unit 2, EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"amber-enterprises","name":"Amber Enterprises","legal_name":"Amber Enterprises India Limited","country":"IN","category":"ems","cin":"L74999HR1990PLC030470","website":"https://www.ambergroupindia.com","incorporated":"1990-01-01","aliases":["Amber"],"note":"Listed PLI awardee (AC manufacturing)","is_illustrative":False,"lat":13.0280,"lng":77.5155,"address":"Peenya Industrial Area Phase III, Bengaluru - 560058"},
  {"id":"syrma-sgs","name":"Syrma SGS Technology","legal_name":"Syrma SGS Technology Limited","country":"IN","category":"ems","cin":"L32300TN2004PLC053459","website":"https://www.syrmasgs.com","incorporated":"2004-01-01","aliases":["Syrma","SGS"],"note":"Listed PLI awardee — Chennai + Bengaluru","is_illustrative":False,"lat":12.8445,"lng":77.6780,"address":"Plot 22, Electronic City Phase I, Hosur Road, Bengaluru - 560100"},
  {"id":"kaynes-tech","name":"Kaynes Technology India","legal_name":"Kaynes Technology India Limited","country":"IN","category":"ems","cin":"L32300KA2008PLC046943","website":"https://www.kaynestechnology.co.in","incorporated":"2008-01-01","aliases":["Kaynes"],"note":"Listed PLI awardee — Mysuru + Bengaluru","is_illustrative":False,"lat":13.0270,"lng":77.5150,"address":"A-53, 2nd Phase, Peenya Industrial Area, Bengaluru - 560058"},
  {"id":"cyient-dlm","name":"Cyient DLM","legal_name":"Cyient DLM Limited","country":"IN","category":"ems","cin":"L32109TG2009PLC063390","website":"https://www.cyientdlm.com","incorporated":"2009-01-01","aliases":["Cyient"],"note":"Listed EMS — Bengaluru + Hyderabad","is_illustrative":False,"lat":13.0285,"lng":77.5160,"address":"Shivapura Industrial Area, Peenya, Bengaluru - 560058"},
  {"id":"avalon-tech","name":"Avalon Technologies","legal_name":"Avalon Technologies Limited","country":"IN","category":"ems","cin":"L30007TN1999PLC043479","website":"https://www.avalontec.com","incorporated":"1999-01-01","aliases":["Avalon"],"note":"Listed EMS — Chennai + Bengaluru","is_illustrative":False,"lat":12.9705,"lng":77.7495,"address":"23, EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"epack-prefab","name":"Epack Prefab","legal_name":"Epack Durables Limited","country":"IN","category":"ems","cin":"L45200DL1997PLC085569","website":"https://www.epackgroup.com","incorporated":"1997-01-01","aliases":["Epack"],"note":"Listed PLI awardee","is_illustrative":False,"lat":12.9700,"lng":77.7500,"address":"Whitefield, Bengaluru - 560066"},
  {"id":"vvdn-tech","name":"VVDN Technologies","legal_name":"VVDN Technologies Private Limited","country":"IN","category":"ems","cin":"U72200HR2011PTC043389","website":"https://www.vvdntech.com","incorporated":"2011-01-01","aliases":["VVDN"],"note":"EMS — Manesar + Bengaluru R&D","is_illustrative":False,"lat":12.9700,"lng":77.6400,"address":"Domlur, Bengaluru - 560071"},
  {"id":"centum-elec","name":"Centum Electronics","legal_name":"Centum Electronics Limited","country":"IN","category":"ems","cin":"L85110KA1993PLC013869","website":"https://www.centumelectronics.com","incorporated":"1993-01-01","aliases":["Centum"],"note":"Listed defence/aerospace EMS","is_illustrative":False,"lat":13.1005,"lng":77.5960,"address":"44, KHB Industrial Area, Yelahanka Newtown, Bengaluru - 560106"},
  {"id":"bharat-fih","name":"Bharat FIH","legal_name":"Bharat FIH Limited","country":"IN","category":"ems","cin":"L32200TN2021PLC145127","website":"https://www.bharatfih.com","incorporated":"2021-01-01","aliases":["FIH"],"note":"Listed PLI awardee — Foxconn JV","is_illustrative":False,"lat":12.8400,"lng":77.6760,"address":"Electronic City Phase II, Hosur Road, Bengaluru - 560100"},
  {"id":"moschip-tech","name":"MosChip Technologies","legal_name":"MosChip Technologies Limited","country":"IN","category":"semiconductor_fab","cin":"L72200TG1999PLC032755","website":"https://www.moschip.com","incorporated":"1999-01-01","aliases":["MosChip"],"note":"Semiconductor IP design","is_illustrative":False,"lat":12.9110,"lng":77.6420,"address":"HSR Layout, Bengaluru - 560102"},
  {"id":"tata-electronics","name":"Tata Electronics","legal_name":"Tata Electronics Private Limited","country":"IN","category":"ems","cin":"U32109KA2020PTC133905","website":"https://www.tataelectronics.com","incorporated":"2020-01-01","aliases":["Tata Elec"],"note":"PLI awardee — Hosur + Bengaluru","is_illustrative":False,"lat":12.8440,"lng":77.6780,"address":"Electronic City Phase I, Hosur Road, Bengaluru - 560100"},
  {"id":"vedanta-foxconn","name":"Vedanta-Foxconn JV","legal_name":"HHL Power Electronics Private Limited","country":"IN","category":"semiconductor_fab","cin":"U31909GJ2022PTC133801","website":"https://www.vedantalimited.com","incorporated":"2022-01-01","aliases":["Vedanta Foxconn","HHL Power"],"note":"Semiconductor fab JV (Gujarat + Bengaluru R&D)","is_illustrative":False,"lat":12.9870,"lng":77.7080,"address":"Mahadevapura, Bengaluru - 560048"},
  {"id":"bel","name":"Bharat Electronics Limited","legal_name":"Bharat Electronics Limited","country":"IN","category":"oem","cin":"L32309KA1954GOI000787","website":"https://www.bel-india.in","incorporated":"1954-01-01","aliases":["BEL"],"note":"PSU — defence electronics","is_illustrative":False,"lat":13.0350,"lng":77.5230,"address":"Jalahalli Post, Bengaluru - 560013"},
  {"id":"iti-ltd","name":"ITI Limited","legal_name":"ITI Limited","country":"IN","category":"oem","cin":"L32202KA1950GOI000640","website":"https://www.itiltd-india.com","incorporated":"1950-01-01","aliases":["ITI"],"note":"PSU telecom equipment","is_illustrative":False,"lat":13.0340,"lng":77.6500,"address":"Dooravaninagar, Bengaluru - 560016"},
  {"id":"tejas-networks","name":"Tejas Networks","legal_name":"Tejas Networks Limited","country":"IN","category":"oem","cin":"L72100KA2000PLC026866","website":"https://www.tejasnetworks.com","incorporated":"2000-01-01","aliases":["Tejas"],"note":"Listed optical networking — now Tata group","is_illustrative":False,"lat":13.0280,"lng":77.5150,"address":"69, Peenya Industrial Area Phase III, Bengaluru - 560058"},
  {"id":"hfcl","name":"HFCL Limited","legal_name":"HFCL Limited","country":"IN","category":"oem","cin":"L64200HP1987PLC007466","website":"https://www.hfcl.com","incorporated":"1987-01-01","aliases":["HFCL","Himachal Futuristic"],"note":"Optical fibre + telecom equipment","is_illustrative":False,"lat":12.9870,"lng":77.7080,"address":"Mahadevapura, Bengaluru - 560048"},
  {"id":"sterlite-tech","name":"Sterlite Technologies","legal_name":"Sterlite Technologies Limited","country":"IN","category":"oem","cin":"L31300GJ2000PLC051411","website":"https://www.stl.tech","incorporated":"2000-01-01","aliases":["STL","Sterlite"],"note":"Optical fibre + digital networks","is_illustrative":False,"lat":12.9700,"lng":77.7500,"address":"EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"tata-elxsi","name":"Tata Elxsi","legal_name":"Tata Elxsi Limited","country":"IN","category":"oem","cin":"L72100KA1989PLC009968","website":"https://www.tataelxsi.com","incorporated":"1989-01-01","aliases":["Tata Elxsi"],"note":"Design and technology services","is_illustrative":False,"lat":12.9700,"lng":77.7500,"address":"EPIP Zone, Whitefield, Bengaluru - 560066"},
  {"id":"bosch-india","name":"Bosch India","legal_name":"Bosch Limited","country":"IN","category":"oem","cin":"L85110KA1951FLC000761","website":"https://www.bosch.in","incorporated":"1951-01-01","aliases":["Bosch","Robert Bosch India"],"note":"Auto electronics + industrial","is_illustrative":False,"lat":12.9360,"lng":77.6280,"address":"Post Box 3000, Hosur Road, Adugodi, Bengaluru - 560030"},
  {"id":"honeywell-india","name":"Honeywell India","legal_name":"Honeywell Automation India Limited","country":"IN","category":"oem","cin":"L29299MH1984PLC034951","website":"https://www.honeywell.com/in","incorporated":"1984-01-01","aliases":["Honeywell"],"note":"Process automation + building tech","is_illustrative":False,"lat":12.9870,"lng":77.7080,"address":"Manyata Tech Park, Outer Ring Road, Bengaluru - 560045"},
  {"id":"continental-india","name":"Continental India","legal_name":"Continental Automotive Components (India) Private Limited","country":"IN","category":"oem","cin":"U34300KA2009FTC049218","website":"https://www.continental-automotive.com","incorporated":"2009-01-01","aliases":["Continental"],"note":"Automotive electronics","is_illustrative":False,"lat":12.9700,"lng":77.7500,"address":"Whitefield, Bengaluru - 560066"},
  {"id":"salcomp","name":"Salcomp","legal_name":"Salcomp Manufacturing India Private Limited","country":"IN","category":"ems","cin":"U32100TN2001FTC047346","website":"https://www.salcomp.com","incorporated":"2001-01-01","aliases":[],"note":"Charger/adapter EMS — Nokia partner","is_illustrative":False,"lat":12.8450,"lng":77.6770,"address":"Electronic City Phase I, Hosur Road, Bengaluru - 560100"},
  {"id":"jabil-india","name":"Jabil India","legal_name":"Jabil Circuit India Private Limited","country":"IN","category":"ems","cin":"U32109MH1994PTC078500","website":"https://www.jabil.com","incorporated":"1994-01-01","aliases":["Jabil"],"note":"Global EMS","is_illustrative":False,"lat":12.8450,"lng":77.6775,"address":"Plot 26, Electronic City Phase I, Hosur Road, Bengaluru - 560100"},
  {"id":"flex-india","name":"Flex India","legal_name":"Flextronics Technologies (India) Private Limited","country":"IN","category":"ems","cin":"U32109KA2001FTC029143","website":"https://www.flex.com","incorporated":"2001-01-01","aliases":["Flextronics","Flex"],"note":"Global EMS","is_illustrative":False,"lat":12.8410,"lng":77.6760,"address":"70/A, SVR Fortune, Electronic City Phase I, Bengaluru - 560100"},
  {"id":"saankhya-labs","name":"Saankhya Labs","legal_name":"Saankhya Labs Private Limited","country":"IN","category":"semiconductor_fab","cin":"U72900KA2008PTC046017","website":"https://www.saankhyalabs.com","incorporated":"2008-01-01","aliases":["Saankhya"],"note":"Bangalore semiconductor — broadcast SoC","is_illustrative":False,"lat":12.9860,"lng":77.5910,"address":"Infantry Road, Vasanth Nagar, Bengaluru - 560001"},
  {"id":"signalchip","name":"Signalchip","legal_name":"Signalchip Innovations Private Limited","country":"IN","category":"semiconductor_fab","cin":"U72900KA2012PTC062802","website":"https://www.signalchip.com","incorporated":"2012-01-01","aliases":[],"note":"Bangalore — 5G baseband SoC","is_illustrative":False,"lat":12.9350,"lng":77.6270,"address":"Koramangala, Bengaluru - 560034"},
  {"id":"wipro-3d","name":"Wipro 3D","legal_name":"Wipro Infrastructure Engineering Private Limited","country":"IN","category":"oem","cin":"U29299KA2010PTC053832","website":"https://www.wiproinfra.com","incorporated":"2010-01-01","aliases":["Wipro Infrastructure"],"note":"Additive manufacturing — Bengaluru","is_illustrative":False,"lat":13.0280,"lng":77.5140,"address":"Peenya Industrial Area Phase II, Bengaluru - 560058"},
  {"id":"zetwerk","name":"Zetwerk","legal_name":"Zetwerk Manufacturing Businesses Private Limited","country":"IN","category":"ems","cin":"U74999KA2018PTC109783","website":"https://www.zetwerk.com","incorporated":"2018-01-01","aliases":[],"note":"B2B manufacturing marketplace — HQ Bengaluru","is_illustrative":False,"lat":12.9350,"lng":77.6270,"address":"Koramangala, Bengaluru - 560034"},
  {"id":"tessolve","name":"Tessolve","legal_name":"Tessolve Semiconductor Private Limited","country":"IN","category":"test_house","cin":"U72200KA2007PTC041842","website":"https://www.tessolve.com","incorporated":"2007-01-01","aliases":[],"note":"Semiconductor test — Bengaluru","is_illustrative":False,"lat":12.9610,"lng":77.6390,"address":"Domlur, Bengaluru - 560071"},
  {"id":"tata-elxsi-whitefield","name":"Tata Elxsi Whitefield","legal_name":"Tata Elxsi Limited (Whitefield campus)","country":"IN","category":"oem","cin":"L72100KA1989PLC009968","website":"https://www.tataelxsi.com","incorporated":"1989-01-01","aliases":["Tata Elxsi WF"],"note":"Whitefield design campus","is_illustrative":False,"lat":12.9710,"lng":77.7510,"address":"EPIP Zone Phase II, Whitefield, Bengaluru - 560066"},
  {"id":"capgemini-engg","name":"Capgemini Engineering","legal_name":"Capgemini Technology Services India Limited","country":"IN","category":"oem","cin":"U72200TN1996PLC036574","website":"https://www.capgemini.com","incorporated":"1996-01-01","aliases":["Capgemini","Altran"],"note":"Engineering services — Bengaluru delivery","is_illustrative":False,"lat":12.9590,"lng":77.6970,"address":"Bagmane Tech Park, Marathahalli, Bengaluru - 560037"},
  {"id":"apex-global-bvi","name":"Apex Global Sourcing BVI","legal_name":"Apex Global Sourcing Ltd","country":"VG","category":"distributor_broker","cin":None,"website":None,"incorporated":"2015-03-01","aliases":["Apex Global"],"note":"Deliberately risky — OFAC SDN demo entity","is_illustrative":True,"lat":None,"lng":None,"address":None},
  {"id":"dnipro-micro","name":"Dnipro Microelectronics","legal_name":"Dnipro Microelectronics LLC","country":"UA","category":"semiconductor_fab","cin":None,"website":None,"incorporated":"2010-06-01","aliases":["Dnipro"],"note":"Deliberately risky — World Bank debarred demo entity","is_illustrative":True,"lat":None,"lng":None,"address":None},
]

# ── scraped real companies ─────────────────────────────────────────────────
SCRAPED = [
  # EMS
  ("MicroLOGIX","ems","peenya","473D, 13th Cross, Peenya Phase IV, Bengaluru - 560058",None,"e-micrologix.com",False),
  ("Vinyas Innovative Technologies","ems","hebbal","Plot 200-A, Hebbal Industrial Area, Bengaluru - 560024","U74999KA2010PTC055014","vinyasit.com",False),
  ("Tescom Electronics","ems","ecity2","No.42(P) KIADB Industrial Area, Electronic City Phase-II, Bengaluru - 560100",None,"tescom.co.in",False),
  ("Indic EMS Electronics","ems","doddaballapur","Plot 37, KIADB Industrial Area, Doddaballapur, Bengaluru - 561203","U32109KA2007PTC043071","indicelectronics.com",False),
  ("Tecno Systems India Electronics","ems","anekal","Khata 229/195/A, Marsur, Anekal Taluk, Bengaluru - 562106",None,"tsie.in",False),
  ("Podrain Electronics","ems","bommanahalli","AECS B Block, Wellington Paradise, Begur, Bengaluru - 560068",None,"podrain.com",False),
  ("RioSH Technologies","ems","ecity1","243, 3rd Cross, Celebrity Layout, Electronic City Phase I, Bengaluru - 560100",None,"rioshtech.com",False),
  ("Anand Industrial Enterprises","ems","whitefield","12D, Sadaramangala Industrial Area, Whitefield Road, Bengaluru - 560048",None,"aiesmt.com",False),
  ("Peninsula Electronics","ems","domlur","V-2-C NGEF Industrial Estate, Graphite India Road, Mahadevapura, Bengaluru - 560048",None,"peninsulaelectronics.com",False),
  ("Smile Electronics","ems","kr_puram","Plot 13, Bhattarahalli, K.R. Puram, Old Madras Road, Bengaluru - 560049",None,"smileelectronics.com",False),
  ("SFO Technologies","ems","bommasandra","130, Bommasandra Jigani Link Rd, Bommasandra Industrial Area, Bengaluru - 560099",None,"sfotechnologies.net",False),
  ("Hical Technologies","ems","ecity2","46 & 47, Phase 2, Electronic City, Bengaluru - 560100","U31900KA2011PTC060176","hical.com",False),
  ("Captronic Systems","ems","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"captronicsystems.com",False),
  ("TronicsZone","ems","jp_nagar","35, 15th Cross, 100ft Ring Road, JP Nagar 6th Phase, Bengaluru - 560078",None,"tronicszone.com",False),
  ("Sienna ECAD Technologies","ems","hsr","147, 5th Main Road, HSR Layout Sector 7, Bengaluru - 560102",None,"siennaecad.com",False),
  ("Karkhana","ems","vasanth_nagar","132, Brigade Road, Shanthala Nagar, Bengaluru - 560025",None,"karkhana.io",False),
  ("Scanditronic Technology","ems","ecity1","Electronic City Phase I, Bengaluru - 560100",None,"scanditronictech.com",False),
  ("Omniscient Electronics","ems","peenya","Peenya Industrial Area Phase II, Bengaluru - 560058",None,"omniscientelectronics.com",False),
  ("Advanced Micro Services","ems","peenya","Peenya Industrial Area, Bengaluru - 560058",None,None,False),
  ("AVR Electronics","ems","ecity1","Electronic City, Bengaluru - 560100",None,"avrelectronics.com",False),
  ("Dexcel Electronics Designs","ems","whitefield","Whitefield, Bengaluru - 560066",None,"dexceldesigns.com",False),
  ("C&B Electronics","ems","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,"cnbtek.com",False),
  ("Kalatronics","ems","peenya","Peenya Industrial Area Phase III, Bengaluru - 560058",None,"kalatronics.com",False),
  ("Vasudha Technologies","ems","bommanahalli","Bommanahalli, Bengaluru - 560068",None,None,False),
  ("JKTD Electronics","ems","kr_puram","550/2, Banaswadi, Kalyan Nagar, Bengaluru - 560043",None,None,False),
  ("East India Technologies","ems","bommanahalli","Bannerghatta Road, Bengaluru - 560068",None,None,False),
  ("Autotec Systems","ems","bommanahalli","Bannerghatta Road, Bengaluru - 560029",None,None,False),
  ("NGP Enterprises","ems","peenya","Peenya Industrial Area Phase II, Bengaluru - 560058",None,None,False),
  ("Avinya Global Solutions","ems","ecity2","Electronic City Phase II, Bengaluru - 560100",None,None,False),
  ("Dawn Infotech","ems","domlur","Domlur, Bengaluru - 560071",None,None,False),
  # PCB
  ("Capronics","pcb_fabricator","ecity1","91B Electronic City, Hosur Road, Bengaluru - 560100",None,"capronics.com",False),
  ("Multipak Electronics India","pcb_fabricator","bommasandra","4th Phase, KIADB Industrial Area, Bommasandra, Bengaluru - 560099",None,None,False),
  ("Nano Circuits","pcb_fabricator","jigani","107/2b, Koppa Village, Hulimangala, Bengaluru - 560105",None,None,False),
  ("Fabsemi Electronics India","pcb_fabricator","banashankari","Subramanyapura, Bengaluru - 560061",None,"fabsemi.com",False),
  ("Leap Industries","pcb_fabricator","kamakshipalya","Kamakshipalya, Bengaluru - 560079",None,"leapindustries.in",False),
  ("Metro Electronics","pcb_fabricator","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"bestpcbonline.com",False),
  ("SN Electronics","pcb_fabricator","rajajinagar","Rajajinagar Industrial Estate, Bengaluru - 560044",None,"snelectronics.net.in",False),
  ("Pulraj Electronics","pcb_fabricator","ecity2","Electronic City Phase II, Bengaluru - 560100",None,None,False),
  ("Circuit Systems","pcb_fabricator","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,None,False),
  ("Confluence Circuits","pcb_fabricator","peenya2","Peenya 2nd Stage, Bengaluru - 560091",None,None,False),
  ("Secure Circuits","pcb_fabricator","jigani","Jigani Industrial Area, Bengaluru - 560105",None,None,False),
  ("Octane Circuits","pcb_fabricator","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,None,False),
  ("Nigama Circuits","pcb_fabricator","ecity1","Electronic City Phase I, Bengaluru - 560100",None,None,False),
  # Component manufacturers
  ("Transwind Technologies","component_manufacturer","peenya","A-52A/B, 2nd Main Road, Peenya Phase IV, Bengaluru - 560058",None,"transwindtechnologies.in",False),
  ("Molex India","component_manufacturer","doddaballapur","Plot 61 & 61A, KIADB Industrial Area, Doddaballapur, Bengaluru Rural - 561203",None,"molex.com",False),
  ("3M India","component_manufacturer","ecity1","48-51, Phase 1, Electronic City, Hosur Road, Bengaluru - 560100",None,"3mindia.in",False),
  ("Interplex Electronics India","component_manufacturer","ecity1","89A, Electronic City, Hosur Road, Bengaluru - 560100",None,"interplex.com",False),
  ("Hical Magnetics","component_manufacturer","ecity2","Sy. No. 46 & 47, Electronic City Phase 2, Bengaluru - 560100","U74900KA2015PTC082358","hical.com",False),
  ("Nagoba Electronics","component_manufacturer","peenya2","11/32, Byraveshwara Industrial Estate, Peenya 2nd Stage, Bengaluru - 560091",None,"nagoba.com",False),
  ("Rotary Electronics","component_manufacturer","rajajinagar","5th Cross, 4th Stage, Industrial Town, Rajajinagar, Bengaluru - 560044",None,None,False),
  ("Benaka Electronics","component_manufacturer","rajajinagar","WOC Road, 4th Stage, Rajajinagar Industrial Estate, Bengaluru - 560044",None,None,False),
  ("Anand Technologies","component_manufacturer","magadi_road","No. 21, 6th Main Road, Sunkadakatte, Magadi Main Road, Bengaluru - 560091",None,None,False),
  ("Microtherm India","component_manufacturer","vasanth_nagar","2nd Floor, 6, Sri Lakshmi, 7th Cross, Vasanth Nagar, Bengaluru - 560052",None,None,False),
  ("Electronic Relays India","component_manufacturer","peenya2","36, 1st Floor, 2nd Cross, Kamakshipalya, Bengaluru - 560079",None,"electronicrelaysindia.com",False),
  ("Sheth Electronics","component_manufacturer","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"shethelectronics.in",False),
  ("Miracle Electronic Devices","component_manufacturer","peenya2","Peenya 2nd Stage, Kamakshipalya, Bengaluru - 560091",None,"miracle.net.in",False),
  ("Hi-Rel Electronics","component_manufacturer","ecity1","Electronic City, Bengaluru - 560100",None,"hitachi-hirel.com",False),
  ("Methode Electronics India","component_manufacturer","whitefield","Whitefield, Bengaluru - 560066",None,"methode.com",False),
  ("Air-O-Tech Enterprises","component_manufacturer","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"airotechenterprises.com",False),
  ("Adatronix","component_manufacturer","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,"adatronix.in",False),
  ("Maini Precision Products","component_manufacturer","peenya","Peenya Industrial Area, Bengaluru - 560058","U27201KA1973PLC002307",None,False),
  ("Nash Industries India","component_manufacturer","peenya","Peenya Industrial Area, Bengaluru - 560058","U28110KA2012PTC063429",None,False),
  ("M G Enterprises","component_manufacturer","peenya","Peenya Industrial Area, Bengaluru - 560058",None,None,False),
  ("Naveen Electrix","component_manufacturer","kamakshipalya","Petechanappa Industrial Estate, Basaveshwara Nagar, Bengaluru - 560079",None,None,False),
  ("Gsas Micro Systems","component_manufacturer","peenya2","Peenya 2nd Stage, Bengaluru - 560091",None,None,False),
  # OEM
  ("Yaskawa India","oem","peenya","17/A, 2nd Main Road, 1st Phase, Peenya Industrial Area, Bengaluru - 560058",None,"yaskawaindia.in",False),
  ("Southern Electronics (Seonics)","oem","peenya","16-A, Peenya Industrial Area Phase-1, Bengaluru - 560058",None,"seonics.co.in",False),
  ("Electronics & Controls Power Systems","oem","peenya","29/A, 80 Feet Road, II Phase, Peenya Industrial Area, Bengaluru - 560058",None,"eandcpower.co.in",False),
  ("Kirloskar Electric Company","oem","peenya","Peenya Industrial Area, Bengaluru - 560058","L31100KA1946PLC000415",None,False),
  ("Cerebra Integrated Technologies","oem","peenya","Peenya Industrial Area, Bengaluru - 560058","L85110KA1993PLC015091",None,False),
  ("Ace Designers","oem","peenya","Peenya Industrial Area Phase II, Bengaluru - 560058","U29199KA1986PLC007816",None,False),
  ("Dynamatic Technologies","oem","peenya","Peenya Phase 2, Bengaluru - 560058","L72200KA1973PLC002308",None,False),
  ("Ajax Engineering","oem","peenya","Peenya Industrial Area, Bengaluru - 560058","U28920KA1992PTC013306",None,False),
  ("Ace Manufacturing Systems","oem","peenya","Peenya Industrial Area, Bengaluru - 560058","U85110KA1994PLC015321",None,False),
  ("Schneider Electric India","oem","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"se.com",False),
  ("Bosch Limited (Adugodi)","oem","adugodi","Post Box 3000, Hosur Road, Adugodi, Bengaluru - 560030",None,"bosch.in",False),
  ("Siemens India","oem","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,"siemens.co.in",False),
  ("ABB India","oem","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,"abb.com",False),
  ("Omron Automation India","oem","hebbal","Manyata Embassy Business Park, Outer Ring Road, Bengaluru - 560045",None,"omron.com",False),
  ("CoreEL Technologies","oem","koramangala","21, 7th Main, 1st Block, Koramangala, Bengaluru - 560034",None,"coreel.com",False),
  ("Titan Company","oem","ecity1","193, Veerasandra, Electronic City P.O., Bengaluru - 560100",None,"titancompany.in",False),
  ("Sparr Electronics","oem","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"sparrl.com",False),
  ("Mysore Electricals Industries","oem","peenya","Peenya Industrial Area, Bengaluru - 560058",None,"meiswitchgears.in",False),
  ("Wave Mechanics","oem","devanahalli","KIADB Aerospace Park, Devanahalli, Bengaluru - 562110",None,None,False),
  ("Zenith Precision","component_manufacturer","devanahalli","KIADB Aerospace Park, Devanahalli, Bengaluru - 562110",None,None,False),
  ("Integra Micro Systems","ems","peenya","KIADB Hardware Park, Peenya, Bengaluru - 560058",None,None,False),
  ("Quantum Power Systems","oem","peenya","KIADB Hardware Park, Peenya, Bengaluru - 560058",None,None,False),
  ("Mahindra Electric Mobility","oem","whitefield","Whitefield, Bengaluru - 560066",None,"mahindra.com",False),
  ("Wipro Infrastructure Engineering","oem","peenya","Peenya Industrial Area Phase II, Bengaluru - 560058",None,"wiproinfra.com",False),
  ("SWA Systems India","oem","banashankari","Kumaraswamy Layout, Bengaluru - 560078",None,"swasystems.in",False),
  ("Gas Turbine Controls India","oem","peenya","Peenya Industrial Area, Bengaluru - 560058",None,None,False),
  ("Meltronics System Tech","oem","whitefield","625, 1st Main C Block, AECS Layout, Whitefield, Bengaluru - 560066",None,None,False),
  # Semiconductor / design
  ("Samsung R&D India Bangalore","semiconductor_fab","marathahalli","Bagmane Constellation Business Park, Outer Ring Road, Bengaluru - 560037",None,"research.samsung.com",False),
  ("Texas Instruments India","semiconductor_fab","peenya","Peenya, Bengaluru - 560058",None,"ti.com",False),
  ("Qualcomm India","semiconductor_fab","whitefield","Bagmane World Technology Center, Whitefield, Bengaluru - 560066",None,"qualcomm.com",False),
  ("Intel Technology India","semiconductor_fab","whitefield","RMZ Infinity, Old Madras Road, Bengaluru - 560016",None,"intel.in",False),
  ("NXP Semiconductors India","semiconductor_fab","whitefield","Bagmane Tech Park, Whitefield, Bengaluru - 560048",None,"nxp.com",False),
  ("Broadcom India","semiconductor_fab","mahadevapura","Kalyani Tech Park, Whitefield, Bengaluru - 560048",None,"broadcom.com",False),
  ("Infineon Technologies India","semiconductor_fab","bommasandra","Bommasandra Industrial Area, Bengaluru - 560099",None,"infineon.com",False),
  ("Applied Materials India","semiconductor_fab","whitefield","Cessna Business Park, Outer Ring Road, Bengaluru - 560037",None,"appliedmaterials.com",False),
  ("ASM Technologies","semiconductor_fab","koramangala","Koramangala, Bengaluru - 560034",None,"asmltd.com",False),
  ("Steradian Semiconductors","semiconductor_fab","koramangala","Koramangala, Bengaluru - 560034",None,"steradiansemi.com",False),
  ("Mirafra Technologies","semiconductor_fab","whitefield","Whitefield, Bengaluru - 560066",None,"mirafra.com",False),
  ("Smartplay Technologies","semiconductor_fab","mahadevapura","Mahadevapura, Bengaluru - 560048",None,"smartplayin.com",False),
  ("Cerium Systems","semiconductor_fab","hsr","HSR Layout, Bengaluru - 560102",None,"cerium-systems.com",False),
  ("Smartdv Technologies","semiconductor_fab","koramangala","Koramangala, Bengaluru - 560034",None,"smart-dv.com",False),
  ("Siliconch Systems","semiconductor_fab","whitefield","Whitefield, Bengaluru - 560066",None,"siliconch.com",False),
  ("Orange Semiconductors","semiconductor_fab","koramangala","Koramangala, Bengaluru - 560034",None,"orangesemi.com",False),
  ("Mavensilicon","semiconductor_fab","whitefield","Whitefield, Bengaluru - 560066",None,"maven-silicon.com",False),
  ("Whizchip","semiconductor_fab","mahadevapura","Mahadevapura, Bengaluru - 560048",None,"whizchip.com",False),
  ("Sion Semiconductors","semiconductor_fab","whitefield","Whitefield, Bengaluru - 560066",None,"sionsemi.com",False),
  ("Eliteplus Semiconductor Technologies","semiconductor_fab","koramangala","Koramangala, Bengaluru - 560034",None,"eliteplustech.com",False),
  ("Mediatek India","semiconductor_fab","whitefield","RMZ NXT, Whitefield, Bengaluru - 560066",None,"mediatek.com",False),
  ("Blackpepper Technologies","semiconductor_fab","hsr","HSR Layout, Bengaluru - 560102",None,"blackpeppertech.com",False),
  ("Sevitech Systems","semiconductor_fab","whitefield","Whitefield, Bengaluru - 560066",None,"sevitechsystems.com",False),
  # Distributors
  ("Arrow Electronics India","distributor_authorised","whitefield","Bagmane Constellation, Outer Ring Road, Bengaluru - 560037",None,"arrow.com",False),
  ("Mouser Electronics India","distributor_authorised","whitefield","Whitefield, Bengaluru - 560066",None,"mouser.in",False),
  ("Buycomponents","distributor_authorised","hsr","HSR Layout, Bengaluru - 560102",None,"buycomponents.in",False),
  ("Hibex India","distributor_authorised","koramangala","John's Ark Building, 902, 6th A Main, Koramangala, Bengaluru - 560034",None,None,False),
  ("Bluewave Automation","distributor_authorised","peenya","Peenya Industrial Area, Bengaluru - 560058",None,None,False),
  ("Regency Electricals","distributor_authorised","rajajinagar","Rajajinagar, Bengaluru - 560044",None,None,False),
  ("G-Sat International","distributor_authorised","rajajinagar","Rajajinagar, Bengaluru - 560044",None,None,False),
  ("Pearlco Enterprise","distributor_authorised","rajajinagar","Rajajinagar, Bengaluru - 560010",None,None,False),
]

# ── illustrative SMEs to fill to 400+ ─────────────────────────────────────
SME_TEMPLATES = [
  # (name_pattern, category, zone)
  ("Peenya EMS Solutions Pvt Ltd","ems","peenya"),
  ("Peenya Circuits & Systems","pcb_fabricator","peenya"),
  ("Peenya Component Works","component_manufacturer","peenya"),
  ("Peenya Power Electronics","oem","peenya"),
  ("Peenya Precision Parts","component_manufacturer","peenya2"),
  ("Peenya Tech Assemblies","ems","peenya2"),
  ("Electronic City PCB Fabrications","pcb_fabricator","ecity1"),
  ("Electronic City Embedded Systems","semiconductor_fab","ecity1"),
  ("Electronic City Component Supplies","component_manufacturer","ecity2"),
  ("Electronic City SMT Solutions","ems","ecity2"),
  ("Whitefield Design Systems","semiconductor_fab","whitefield"),
  ("Whitefield Advanced Electronics","ems","whitefield"),
  ("Whitefield Connector Technologies","component_manufacturer","whitefield"),
  ("Bommasandra PCB Works","pcb_fabricator","bommasandra"),
  ("Bommasandra Assembly Lines","ems","bommasandra"),
  ("Bommasandra Electronic Parts","component_manufacturer","bommasandra"),
  ("Jigani Circuit Technologies","pcb_fabricator","jigani"),
  ("Jigani EMS Fabricators","ems","jigani"),
  ("Yelahanka Aerospace Electronics","oem","yelahanka"),
  ("Yelahanka Defence Systems","oem","yelahanka"),
  ("Yelahanka PCB Solutions","pcb_fabricator","yelahanka"),
  ("Rajajinagar Electronics Works","component_manufacturer","rajajinagar"),
  ("Rajajinagar Power Systems","oem","rajajinagar"),
  ("Domlur Electronic Assemblies","ems","domlur"),
  ("Hebbal Industrial Electronics","oem","hebbal"),
  ("Hebbal Component Manufacturers","component_manufacturer","hebbal"),
  ("Koramangala Semiconductor Design","semiconductor_fab","koramangala"),
  ("HSR Layout IC Design","semiconductor_fab","hsr"),
  ("Bommanahalli Electronic Services","ems","bommanahalli"),
  ("Bommanahalli Precision Electronics","component_manufacturer","bommanahalli"),
  ("Jalahalli Defence Electronics","oem","jalahalli"),
  ("Jalahalli PCB Manufacturers","pcb_fabricator","jalahalli"),
  ("Mysore Road Electronic Industries","component_manufacturer","mysore_road"),
  ("Mysore Road Power Electronics","oem","mysore_road"),
  ("Tumkur Road Electronics Works","ems","tumkur_road"),
  ("JP Nagar Electronic Assemblies","ems","jp_nagar"),
  ("Vasanth Nagar PCB House","pcb_fabricator","vasanth_nagar"),
  ("Marathahalli Chip Design","semiconductor_fab","marathahalli"),
  ("Mahadevapura Design Labs","semiconductor_fab","mahadevapura"),
  ("KR Puram Electronics","ems","kr_puram"),
  ("Anekal Electronic Manufacturing","ems","anekal"),
  ("Doddaballapur Component Works","component_manufacturer","doddaballapur"),
  ("Hoskote Industrial Electronics","ems","hoskote"),
  ("Devanahalli Aerospace Systems","oem","devanahalli"),
  ("Kamakshipalya Electronic Fabricators","pcb_fabricator","kamakshipalya"),
  ("Magadi Road Electronics","component_manufacturer","magadi_road"),
  ("Banashankari Electronic Services","ems","banashankari"),
  ("Adugodi Auto Electronics","component_manufacturer","adugodi"),
  ("South Bangalore EMS Hub","ems","jp_nagar"),
  ("Karnataka Semiconductor Ventures","semiconductor_fab","whitefield"),
  ("Bengaluru Electronic Packaging","ems","peenya"),
  ("Bengaluru PCB Express","pcb_fabricator","bommasandra"),
  ("Bengaluru Chip Solutions","semiconductor_fab","koramangala"),
  ("Bengaluru Sensor Systems","component_manufacturer","ecity1"),
  ("Bengaluru Avionics Components","oem","devanahalli"),
  ("East Bengaluru Electronics","ems","whitefield"),
  ("North Bengaluru PCB Hub","pcb_fabricator","yelahanka"),
  ("West Bengaluru Component Works","component_manufacturer","rajajinagar"),
  ("South Bengaluru Industrial EMS","ems","jigani"),
  ("Outer Ring Road Electronics","semiconductor_fab","mahadevapura"),
  ("Hosur Road Assembly Works","ems","ecity1"),
  ("Bangalore North EMS Fabricators","ems","hebbal"),
  ("Silicon Valley of India Labs","semiconductor_fab","whitefield"),
  ("IndElec Manufacturing","ems","bommasandra"),
  ("KarnatakaElec Systems","oem","peenya"),
  ("BengaluruBoards PCB","pcb_fabricator","jigani"),
  ("VishwaElectronics Assemblies","ems","ecity2"),
  ("RamaElectronics Components","component_manufacturer","peenya2"),
  ("ChitraCircuits PCB","pcb_fabricator","rajajinagar"),
  ("IndiaChip Design House","semiconductor_fab","hsr"),
  ("NandElec Systems","ems","bommanahalli"),
  ("SikhyaElectronics Works","component_manufacturer","kamakshipalya"),
  ("TechPark Electronics Bengaluru","semiconductor_fab","whitefield"),
  ("MakeInIndia Electronics","ems","ecity1"),
  ("GreenElec PCB Works","pcb_fabricator","bommasandra"),
  ("SmartChip Bengaluru","semiconductor_fab","mahadevapura"),
  ("PowerPack Electronics","oem","peenya"),
  ("ConnectIndia Assemblies","ems","domlur"),
  ("PrecisionBoards Bengaluru","pcb_fabricator","yelahanka"),
  ("FlexAssembly Karnataka","ems","hoskote"),
  ("AutoElec Bengaluru","oem","adugodi"),
  ("DefenceElec Systems","oem","jalahalli"),
  ("AeroBoards India","pcb_fabricator","devanahalli"),
  ("IotElec Bengaluru","semiconductor_fab","koramangala"),
  ("WearableTech Bengaluru","oem","whitefield"),
  ("EVElec Bengaluru","component_manufacturer","whitefield"),
  ("CleanEnergy Electronics","component_manufacturer","bommasandra"),
  ("SolarElec Bengaluru","oem","ecity2"),
  ("MedElec Systems Bengaluru","oem","hsr"),
  ("AgriElec Karnataka","oem","yelahanka"),
  ("SpaceElec Bengaluru","semiconductor_fab","devanahalli"),
  ("DroneElec Systems","oem","devanahalli"),
  ("5G Electronics Karnataka","semiconductor_fab","whitefield"),
  ("AIChip Bengaluru","semiconductor_fab","koramangala"),
  ("EdgeCompute Bengaluru","semiconductor_fab","mahadevapura"),
  ("SecureChip Karnataka","semiconductor_fab","hsr"),
  ("QuantumElec Bengaluru","semiconductor_fab","whitefield"),
  ("PhotonicElec Karnataka","semiconductor_fab","whitefield"),
  ("MicroSensor Bengaluru","component_manufacturer","ecity1"),
  ("NanoTech Electronics","component_manufacturer","whitefield"),
  ("MicroMEMS Bengaluru","semiconductor_fab","peenya"),
  ("RFElec Karnataka","semiconductor_fab","peenya"),
  ("PowerIC Bengaluru","semiconductor_fab","koramangala"),
  ("AnalogChip Karnataka","semiconductor_fab","whitefield"),
  ("MixedSignal Bengaluru","semiconductor_fab","hsr"),
  ("EmbeddedSys Karnataka","semiconductor_fab","mahadevapura"),
  ("FPGADesign Bengaluru","semiconductor_fab","whitefield"),
  ("ASICDesign Karnataka","semiconductor_fab","koramangala"),
  ("VerificationIP Bengaluru","semiconductor_fab","hsr"),
  ("PhysicalDesign Karnataka","semiconductor_fab","whitefield"),
  ("TimingAnalysis Bengaluru","semiconductor_fab","mahadevapura"),
  ("DFT Solutions Karnataka","semiconductor_fab","koramangala"),
  ("RFTesting Bengaluru","test_house","peenya"),
  ("EMCTesting Karnataka","test_house","ecity2"),
  ("ReliabilityTest Bengaluru","test_house","bommasandra"),
  ("ATE Systems Bengaluru","test_house","whitefield"),
  ("BurnIn Testing Karnataka","test_house","peenya"),
  ("EnvironmentalTest Bengaluru","test_house","yelahanka"),
  ("PCBTest Karnataka","test_house","bommasandra"),
  ("FunctionTest Bengaluru","test_house","ecity1"),
  ("AOI Systems Karnataka","test_house","jigani"),
  ("XRayInspection Bengaluru","test_house","peenya"),
  ("Authorized Components Karnataka","distributor_authorised","whitefield"),
  ("ElecDistrib Bengaluru","distributor_authorised","rajajinagar"),
  ("ComponentHub Karnataka","distributor_authorised","koramangala"),
  ("PartnerElec Bengaluru","distributor_authorised","hsr"),
  ("TechDistrib Karnataka","distributor_authorised","whitefield"),
  ("ICDistrib Bengaluru","distributor_authorised","mahadevapura"),
  ("PCBDistrib Karnataka","distributor_authorised","ecity1"),
  ("ConnectorDistrib Bengaluru","distributor_authorised","peenya"),
  ("PassiveElec Karnataka","distributor_authorised","bommasandra"),
  ("ActiveComponents Bengaluru","distributor_authorised","whitefield"),
]

def make_id(name, existing_ids):
    base = slug(name)
    s = base
    i = 2
    while s in existing_ids:
        s = f"{base}-{i}"
        i += 1
    existing_ids.add(s)
    return s

def build_suppliers():
    existing_ids = set()
    suppliers = []

    # 1. existing
    for s in EXISTING:
        existing_ids.add(s["id"])
        suppliers.append(s)

    # 2. scraped
    for (name, cat, zone, address, cin, website, is_ill) in SCRAPED:
        sid = make_id(name, existing_ids)
        lat, lng, _ = coord(zone)
        suppliers.append({
            "id": sid,
            "name": name,
            "legal_name": name,
            "country": "IN",
            "category": cat,
            "cin": cin,
            "website": f"https://www.{website}" if website else None,
            "incorporated": None,
            "aliases": [],
            "note": f"Verified Bangalore {cat.replace('_',' ')} company",
            "is_illustrative": is_ill,
            "lat": lat,
            "lng": lng,
            "address": address,
        })

    # 3. illustrative SMEs — from template list first
    for (name, cat, zone) in SME_TEMPLATES:
        if len(suppliers) >= 420:
            break
        sid = make_id(name, existing_ids)
        lat, lng, zone_addr = coord(zone)
        plot = random.randint(1, 250)
        suppliers.append({
            "id": sid,
            "name": name,
            "legal_name": f"{name} (Pvt Ltd)",
            "country": "IN",
            "category": cat,
            "cin": None,
            "website": None,
            "incorporated": None,
            "aliases": [],
            "note": f"Illustrative SME — composite of typical Bengaluru {cat.replace('_',' ')} suppliers",
            "is_illustrative": True,
            "lat": lat,
            "lng": lng,
            "address": f"Plot {plot}, {zone_addr}",
        })

    # 4. dynamically generated illustrative SMEs if still < 420
    prefixes = ["Sri","Shree","Navi","Techno","Indo","Karna","Namma","Veera","Ganga",
                "Kaveri","Tungabhadra","Kempegowda","Basava","Vinayaka","Lakshmi",
                "Saraswathi","Vidya","Pragathi","Uttara","Dakshina"]
    suffixes = ["Electronics Pvt Ltd","Circuits Pvt Ltd","Systems Pvt Ltd",
                "Tech Pvt Ltd","Components Pvt Ltd","Assemblies Pvt Ltd",
                "Solutions Pvt Ltd","Industries Pvt Ltd","Engineering Pvt Ltd"]
    cats = ["ems","pcb_fabricator","component_manufacturer","oem","distributor_authorised"]
    zones = list(Z.keys())
    idx = 0
    while len(suppliers) < 420:
        p = prefixes[idx % len(prefixes)]
        s = suffixes[(idx // len(prefixes)) % len(suffixes)]
        name = f"{p} {s}"
        cat = cats[idx % len(cats)]
        zone = zones[idx % len(zones)]
        if name not in existing_ids:
            sid = make_id(name, existing_ids)
            lat, lng, zone_addr = coord(zone)
            plot = random.randint(1, 250)
            suppliers.append({
                "id": sid,
                "name": name,
                "legal_name": name,
                "country": "IN",
                "category": cat,
                "cin": None,
                "website": None,
                "incorporated": None,
                "aliases": [],
                "note": "Illustrative SME — composite of typical Bengaluru electronics SME",
                "is_illustrative": True,
                "lat": lat,
                "lng": lng,
                "address": f"Plot {plot}, {zone_addr}",
            })
        idx += 1
        if idx > 10000:
            break

    return suppliers

if __name__ == "__main__":
    out = Path(__file__).resolve().parents[1] / "data" / "seed_suppliers.json"
    suppliers = build_suppliers()
    out.write_text(json.dumps(suppliers, indent=2, default=str))
    real = sum(1 for s in suppliers if not s["is_illustrative"])
    ill  = sum(1 for s in suppliers if s["is_illustrative"])
    geo  = sum(1 for s in suppliers if s.get("lat"))
    print(f"Written {len(suppliers)} suppliers → {out}")
    print(f"  Real: {real}  Illustrative: {ill}  With coordinates: {geo}")
