# PhantomWatch — Purple Team Automation Platform

Simulate MITRE ATT&CK techniques → validate detections → generate Sigma rules → push to SIEM.

**Features:**
- 11 real macOS atomics (discovery, execution, persistence, credential access)
- Live MITRE ATT&CK data feed (697 techniques)
- Detection validation with 9 hand-crafted rules
- Auto Sigma generation with FP tuning
- 4 campaign profiles (apt-macos, discovery-only, exec-persist, cred-harvest)
- Coverage matrix with A–F grades
- ATT&CK Navigator export
- REST API + single-page web dashboard
- APScheduler with drift detection
- Elastic + Splunk integration
- GitHub Actions CI/CD

**Quick start:**
```bash
pip install -r requirements.txt
python server.py
open http://localhost:5000
```

**CLI:**
```bash
python main.py campaign --profile apt-macos --open
python main.py run --technique T1082 --validate
python main.py profiles
```

**API:**
```bash
curl -X POST http://localhost:5000/api/campaigns -d '{"profile":"apt-macos"}'
curl http://localhost:5000/api/campaigns/profiles
curl http://localhost:5000/api/sigma
```

**Author:** Ahad Shaikh | Portfolio project #6
