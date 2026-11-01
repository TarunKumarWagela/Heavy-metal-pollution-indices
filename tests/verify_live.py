import urllib.request, json

def post(url, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
    r = urllib.request.urlopen(req, timeout=5)
    return json.loads(r.read()), r.status

meas = {"Pb": 0.015, "Cd": 0.002, "Cr": 0.030}
stds = {"Pb": 0.010, "Cd": 0.003, "Cr": 0.050}

r, s = post("http://127.0.0.1:5000/api/calculate/hpi", {"measurements": meas, "standards": stds})
hpi = r["hpi"]
ok = "PASS" if abs(hpi - 84.754902) < 0.001 else "FAIL"
print(f"  HPI={hpi:.6f}  expected=84.754902  [{ok}]")

# Check per-metal contributions
pm = {p["metal"]: p for p in r["per_metal"]}
for metal, exp_pct in [("Pb",39.039908),("Cd",57.836900),("Cr",3.123192)]:
    actual = pm[metal]["percentage_contribution"]
    ok2 = "PASS" if abs(actual - exp_pct) < 0.001 else "FAIL"
    print(f"    {metal} pct_contrib={actual:.6f}  expected={exp_pct}  [{ok2}]")

r2, _ = post("http://127.0.0.1:5000/api/calculate/hei", {"measurements": meas, "standards": stds})
hei = r2["hei"]
ok = "PASS" if abs(hei - 2.766667) < 0.001 else "FAIL"
print(f"  HEI={hei:.6f}  expected=2.766667  [{ok}]")

r3, _ = post("http://127.0.0.1:5000/api/calculate/cd", {"measurements": meas, "reference_values": stds})
cd = r3["cd_index"]
ok = "PASS" if abs(cd - (-0.233333)) < 0.001 else "FAIL"
print(f"  Cd_index={cd:.6f}  expected=-0.233333  [{ok}]")

r4, _ = post("http://127.0.0.1:5000/api/soil/calculate/pli", {
    "measurements":      {"Pb": 60.0, "Cd": 1.05, "Cr": 210.0},
    "background_values": {"Pb": 20.0, "Cd": 0.35, "Cr":  70.0}
})
pli = r4["pli"]
ok = "PASS" if abs(pli - 3.0) < 0.001 else "FAIL"
print(f"  PLI={pli:.6f}  expected=3.0  [{ok}]")
print("Domain check:", r4.get("domain"))
