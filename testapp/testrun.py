import urllib.request, urllib.parse, json, re, html as htmllib

UA = "FactDropHarvester/1.0 (test)"
API = "https://en.wikipedia.org/w/api.php"

url = API + "?action=query&list=allpages&apnamespace=4&apprefix=Recent+additions%2F&aplimit=5&format=json&formatversion=2"
req = urllib.request.Request(url, headers={"User-Agent": UA})
d = json.load(urllib.request.urlopen(req, timeout=30))

title = d["query"]["allpages"][0]["title"]
print("Checking:", title)

url2 = API + "?action=parse&page=" + urllib.parse.quote(title) + "&prop=text&format=json&formatversion=2"
req2 = urllib.request.Request(url2, headers={"User-Agent": UA})
page = json.load(urllib.request.urlopen(req2, timeout=30))
raw = page["parse"]["text"]

items = re.findall(r"<li>(.*?)</li>", raw, re.S)
print(f"Found {len(items)} list items. First 5:")
for item in items[:5]:
    clean = htmllib.unescape(re.sub(r"<[^>]+>", "", item)).strip()
    print(repr(clean[:200]))
    print()
