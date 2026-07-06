"""
reporter.py — v2
Self-contained HTML dashboard with campaign timeline,
coverage matrix section, and tuned Sigma download.
"""

import json
import base64
import logging
from datetime import datetime, timezone
from pathlib  import Path
from rich.console import Console

console = Console()
logger  = logging.getLogger(__name__)


class Reporter:
    def __init__(self, output_dir: str = "reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def generate(self, results, sigma_rules=None, meta=None, outfile=None) -> str:
        sigma_rules = sigma_rules or []
        meta        = meta        or {}
        stats       = self._compute_stats(results)
        heatmap     = self._build_heatmap(results)
        html        = self._render(results, sigma_rules, meta, stats, heatmap)
        ts          = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        filename    = outfile or f"reports/phantomwatch_{ts}.html"
        Path(filename).write_text(html, encoding="utf-8")
        console.print(f"[bold green]✓ Report saved → {filename}[/bold green]")
        return filename

    def _compute_stats(self, results):
        simulated = [r for r in results if r.status == "simulated"]
        detected  = [r for r in simulated if getattr(r, "detected", False)]
        gaps      = [r for r in simulated if not getattr(r, "detected", True)]
        coverage  = round(len(detected) / len(simulated) * 100, 1) if simulated else 0
        tactic_stats = {}
        for r in simulated:
            tactic = r.tactics[0] if r.tactics else "unknown"
            tactic_stats.setdefault(tactic, {"detected": 0, "total": 0})
            tactic_stats[tactic]["total"] += 1
            if getattr(r, "detected", False):
                tactic_stats[tactic]["detected"] += 1
        return {
            "total":        len(results),
            "simulated":    len(simulated),
            "detected":     len(detected),
            "gaps":         len(gaps),
            "errors":       len([r for r in results if r.status == "error"]),
            "skipped":      len([r for r in results if r.status == "skipped"]),
            "coverage":     coverage,
            "tactic_stats": tactic_stats,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

    def _build_heatmap(self, results):
        tactic_map = {}
        for r in results:
            if r.status != "simulated":
                continue
            tactic = r.tactics[0] if r.tactics else "unknown"
            tactic_map.setdefault(tactic, []).append(r)
        heatmap = []
        for tactic, techs in sorted(tactic_map.items()):
            detected = sum(1 for t in techs if getattr(t, "detected", False))
            total    = len(techs)
            pct      = round(detected / total * 100) if total else 0
            heatmap.append({
                "tactic":   tactic.replace("-", " ").title(),
                "detected": detected,
                "total":    total,
                "pct":      pct,
            })
        return heatmap

    def _render(self, results, sigma_rules, meta, stats, heatmap) -> str:
        # ── Sigma bundle ───────────────────────────────────────────
        for bundle_name in [
            "sigma_rules/tuned/phantomwatch_tuned_bundle.yml",
            "sigma_rules/phantomwatch_bundle.yml",
        ]:
            bp = Path(bundle_name)
            if bp.exists():
                bundle_b64 = base64.b64encode(bp.read_bytes()).decode()
                bundle_label = "Tuned " if "tuned" in bundle_name else ""
                break
        else:
            bundle_b64   = base64.b64encode(b"# No bundle found").decode()
            bundle_label = ""

        # ── Results table rows ─────────────────────────────────────
        rows_html = ""
        for r in results:
            if r.status != "simulated":
                continue
            detail    = getattr(r, "detection_detail", {})
            status    = detail.get("status", "unknown")
            conf      = detail.get("confidence") or "—"
            rules_hit = ", ".join(detail.get("rules", [])) or "—"
            tactic    = r.tactics[0].replace("-"," ").title() if r.tactics else "—"
            det_class = {
                "detected":   "badge-detected",
                "undetected": "badge-gap",
                "partial":    "badge-partial",
            }.get(status, "badge-unknown")
            tel       = getattr(r, "telemetry", {}) or {}
            ioc_count = len(tel.get("iocs", []))
            duration  = f"{tel.get('duration_ms', 0):.0f}ms" if tel else "stub"
            rows_html += f"""
            <tr>
              <td><code>{r.technique_id}</code></td>
              <td>{r.name[:55]}</td>
              <td>{tactic}</td>
              <td><span class="badge {det_class}">{status}</span></td>
              <td>{conf}</td>
              <td>{rules_hit}</td>
              <td>{ioc_count}</td>
              <td>{duration}</td>
            </tr>"""

        # ── Heatmap bars ───────────────────────────────────────────
        heatmap_html = ""
        for cell in heatmap:
            pct   = cell["pct"]
            color = "#00ff9f" if pct >= 70 else "#ffd700" if pct >= 40 else "#ff4d4d"
            heatmap_html += f"""
            <div class="heatmap-row">
              <div class="heatmap-label">{cell['tactic']}</div>
              <div class="heatmap-bar-wrap">
                <div class="heatmap-bar" style="width:{max(pct,1)}%;background:{color}"></div>
              </div>
              <div class="heatmap-stat">{cell['detected']}/{cell['total']} ({pct}%)</div>
            </div>"""

        # ── Campaign timeline ──────────────────────────────────────
        tactics     = meta.get("tactics", [])
        started_at  = meta.get("started_at", "—")
        finished_at = meta.get("finished_at", "—")
        campaign    = meta.get("campaign", "—")
        profile     = meta.get("profile", "—")

        timeline_html = ""
        tactic_stats  = stats["tactic_stats"]
        for i, tactic in enumerate(tactics, 1):
            s     = tactic_stats.get(tactic, {"detected": 0, "total": 0})
            pct   = round(s["detected"] / s["total"] * 100) if s["total"] else 0
            color = "#00ff9f" if pct >= 70 else "#ffd700" if pct >= 40 else "#ff4d4d"
            timeline_html += f"""
            <div class="timeline-step">
              <div class="timeline-num">{i}</div>
              <div class="timeline-body">
                <div class="timeline-tactic">{tactic.replace('_',' ').upper()}</div>
                <div class="timeline-stats">
                  {s['total']} techniques ·
                  <span style="color:{color}">{s['detected']} detected</span> ·
                  {s['total'] - s['detected']} gaps
                </div>
              </div>
              <div class="timeline-pct" style="color:{color}">{pct}%</div>
            </div>"""

        if not timeline_html:
            timeline_html = '<p class="no-data">No campaign timeline — run with campaign command.</p>'

        # ── Sigma cards ────────────────────────────────────────────
        sigma_html = ""
        for rule in sigma_rules[:30]:
            sigma_html += f"""
            <div class="sigma-card">
              <div class="sigma-header">
                <span class="sigma-id">{rule.rule_id}</span>
                <span class="sigma-tech">{rule.technique_id}</span>
              </div>
              <div class="sigma-name">{rule.name}</div>
              <div class="sigma-tactic">{rule.tactic}</div>
              <pre class="sigma-yaml">{rule.to_yaml()[:600]}</pre>
            </div>"""
        if not sigma_html:
            sigma_html = '<p class="no-data">No Sigma rules — run with --validate flag.</p>'

        cov_color = (
            "#00ff9f" if stats["coverage"] >= 70 else
            "#ffd700" if stats["coverage"] >= 40 else
            "#ff4d4d"
        )

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PhantomWatch Report</title>
  <style>
    :root {{
      --bg:      #0a0e1a;
      --surface: #111827;
      --border:  #1f2937;
      --accent:  #00d4ff;
      --green:   #00ff9f;
      --red:     #ff4d4d;
      --yellow:  #ffd700;
      --text:    #e2e8f0;
      --muted:   #64748b;
      --font:    'Segoe UI', system-ui, sans-serif;
      --mono:    'JetBrains Mono', 'Fira Code', monospace;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ background: var(--bg); color: var(--text); font-family: var(--font); }}

    header {{
      background: linear-gradient(135deg, #0a0e1a 0%, #111827 100%);
      border-bottom: 1px solid var(--border);
      padding: 2rem 2.5rem;
      display: flex; justify-content: space-between; align-items: center;
    }}
    .logo {{ display: flex; align-items: center; gap: 1rem; }}
    .logo-icon {{
      width: 42px; height: 42px;
      background: linear-gradient(135deg, var(--accent), var(--green));
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 1.4rem;
    }}
    .logo h1 {{ font-size: 1.5rem; letter-spacing: 0.05em; color: var(--accent); }}
    .logo p  {{ font-size: 0.75rem; color: var(--muted); margin-top: 2px; }}
    .header-right {{ text-align: right; font-size: 0.8rem; color: var(--muted); }}
    .header-right strong {{ color: var(--text); }}
    .btn-download {{
      display: inline-flex; align-items: center; gap: 0.5rem;
      background: linear-gradient(135deg, var(--accent), #0099bb);
      color: #0a0e1a; font-weight: 700; font-size: 0.82rem;
      padding: 0.55rem 1.1rem; border-radius: 6px;
      text-decoration: none; border: none; cursor: pointer;
      margin-top: 0.5rem; transition: opacity 0.2s;
    }}
    .btn-download:hover {{ opacity: 0.85; }}

    main {{ max-width: 1400px; margin: 0 auto; padding: 2rem 2.5rem; }}
    section {{ margin-bottom: 2.5rem; }}
    h2 {{
      font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase;
      color: var(--accent); margin-bottom: 1.2rem; padding-bottom: 0.5rem;
      border-bottom: 1px solid var(--border);
    }}

    .stats-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1rem;
    }}
    .stat-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.2rem 1rem; text-align: center;
    }}
    .stat-value {{ font-size: 2.2rem; font-weight: 800; font-family: var(--mono); }}
    .stat-label {{
      font-size: 0.72rem; color: var(--muted);
      text-transform: uppercase; letter-spacing: 0.08em; margin-top: 0.4rem;
    }}

    /* Campaign meta */
    .campaign-meta {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem; margin-bottom: 1.5rem;
    }}
    .meta-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 0.9rem 1rem;
    }}
    .meta-label {{ font-size: 0.68rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }}
    .meta-value {{ font-size: 0.9rem; color: var(--text); font-weight: 600; margin-top: 0.25rem; font-family: var(--mono); }}

    /* Timeline */
    .timeline {{ display: flex; flex-direction: column; gap: 0.75rem; }}
    .timeline-step {{
      display: grid; grid-template-columns: 36px 1fr 60px;
      align-items: center; gap: 1rem;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 0.9rem 1rem;
    }}
    .timeline-num {{
      width: 32px; height: 32px; border-radius: 50%;
      background: linear-gradient(135deg, var(--accent), var(--green));
      color: #0a0e1a; font-weight: 800; font-size: 0.82rem;
      display: flex; align-items: center; justify-content: center;
    }}
    .timeline-tactic {{ font-size: 0.82rem; font-weight: 700; color: var(--text); letter-spacing: 0.05em; }}
    .timeline-stats  {{ font-size: 0.75rem; color: var(--muted); margin-top: 0.2rem; }}
    .timeline-pct    {{ font-size: 1.1rem; font-weight: 800; font-family: var(--mono); text-align: right; }}

    /* Heatmap */
    .heatmap {{ display: flex; flex-direction: column; gap: 0.6rem; }}
    .heatmap-row {{
      display: grid; grid-template-columns: 200px 1fr 120px;
      align-items: center; gap: 1rem;
    }}
    .heatmap-label  {{ font-size: 0.82rem; }}
    .heatmap-bar-wrap {{ background: var(--border); border-radius: 4px; height: 18px; overflow: hidden; }}
    .heatmap-bar    {{ height: 100%; border-radius: 4px; }}
    .heatmap-stat   {{ font-size: 0.78rem; color: var(--muted); font-family: var(--mono); text-align: right; }}

    /* Table */
    .table-wrap {{ overflow-x: auto; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.82rem; }}
    thead tr {{ background: var(--surface); border-bottom: 2px solid var(--border); }}
    th {{
      padding: 0.75rem 1rem; text-align: left;
      font-size: 0.68rem; text-transform: uppercase;
      letter-spacing: 0.08em; color: var(--muted);
    }}
    tbody tr {{ border-bottom: 1px solid var(--border); transition: background 0.15s; }}
    tbody tr:hover {{ background: rgba(0,212,255,0.04); }}
    td {{ padding: 0.65rem 1rem; vertical-align: middle; }}
    code {{
      background: rgba(0,212,255,0.08); color: var(--accent);
      padding: 2px 6px; border-radius: 4px;
      font-family: var(--mono); font-size: 0.8rem;
    }}

    .badge {{
      display: inline-block; font-size: 0.68rem; font-weight: 600;
      padding: 2px 8px; border-radius: 20px; letter-spacing: 0.05em;
      text-transform: uppercase;
    }}
    .badge-detected {{ background: rgba(0,255,159,0.15); color: var(--green); }}
    .badge-gap      {{ background: rgba(255,77,77,0.15);  color: var(--red);   }}
    .badge-partial  {{ background: rgba(255,215,0,0.15);  color: var(--yellow);}}
    .badge-unknown  {{ background: rgba(100,116,139,0.2); color: var(--muted); }}

    /* Sigma */
    .sigma-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(380px, 1fr)); gap: 1rem; }}
    .sigma-card {{
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 10px; padding: 1.1rem; overflow: hidden;
    }}
    .sigma-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem; }}
    .sigma-id   {{ font-family: var(--mono); font-size: 0.75rem; color: var(--accent); font-weight: 700; }}
    .sigma-tech {{
      font-family: var(--mono); font-size: 0.72rem; color: var(--muted);
      background: var(--border); padding: 2px 7px; border-radius: 4px;
    }}
    .sigma-name   {{ font-size: 0.85rem; font-weight: 600; margin-bottom: 0.2rem; }}
    .sigma-tactic {{
      font-size: 0.7rem; color: var(--yellow);
      text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 0.75rem;
    }}
    .sigma-yaml {{
      background: #0a0e1a; border: 1px solid var(--border);
      border-radius: 6px; padding: 0.75rem;
      font-family: var(--mono); font-size: 0.7rem;
      color: #94a3b8; overflow-x: auto; max-height: 200px;
      overflow-y: auto; white-space: pre; line-height: 1.5;
    }}

    .search-bar {{
      width: 100%; max-width: 360px;
      background: var(--surface); border: 1px solid var(--border);
      border-radius: 8px; padding: 0.55rem 1rem;
      color: var(--text); font-size: 0.85rem;
      outline: none; margin-bottom: 1rem;
    }}
    .search-bar:focus {{ border-color: var(--accent); }}

    footer {{
      text-align: center; padding: 2rem;
      font-size: 0.75rem; color: var(--muted);
      border-top: 1px solid var(--border); margin-top: 2rem;
    }}
    footer span {{ color: var(--accent); }}
    .no-data {{ color: var(--muted); font-size: 0.85rem; padding: 1rem 0; }}
  </style>
</head>
<body>

<header>
  <div class="logo">
    <div class="logo-icon">👻</div>
    <div>
      <h1>PHANTOMWATCH</h1>
      <p>Purple Team Automation Platform</p>
    </div>
  </div>
  <div class="header-right">
    <div>Generated: <strong>{stats["generated_at"]}</strong></div>
    <div>Session: <strong>{meta.get("session_id", "—")[:8]}</strong></div>
    <button class="btn-download" onclick="downloadBundle()">
      ⬇ Download {bundle_label}Sigma Bundle
    </button>
  </div>
</header>

<main>

  <!-- Run Summary -->
  <section>
    <h2>Run Summary</h2>
    <div class="stats-grid">
      <div class="stat-card">
        <div class="stat-value" style="color:{cov_color}">{stats["coverage"]}%</div>
        <div class="stat-label">Coverage</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--green)">{stats["detected"]}</div>
        <div class="stat-label">Detected</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--red)">{stats["gaps"]}</div>
        <div class="stat-label">Gaps</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--accent)">{stats["simulated"]}</div>
        <div class="stat-label">Simulated</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--muted)">{stats["skipped"]}</div>
        <div class="stat-label">Skipped</div>
      </div>
      <div class="stat-card">
        <div class="stat-value" style="color:var(--yellow)">{len(sigma_rules)}</div>
        <div class="stat-label">Sigma Rules</div>
      </div>
    </div>
  </section>

  <!-- Campaign Info -->
  <section>
    <h2>Campaign</h2>
    <div class="campaign-meta">
      <div class="meta-card">
        <div class="meta-label">Profile</div>
        <div class="meta-value">{profile}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Name</div>
        <div class="meta-value">{campaign}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">Session ID</div>
        <div class="meta-value">{meta.get("session_id","—")[:8]}</div>
      </div>
      <div class="meta-card">
        <div class="meta-label">ATT&CK Version</div>
        <div class="meta-value">{meta.get("attack_version","v14")}</div>
      </div>
    </div>

    <!-- Timeline -->
    <div class="timeline">
      {timeline_html}
    </div>
  </section>

  <!-- Heatmap -->
  <section>
    <h2>Tactic Coverage Heatmap</h2>
    <div class="heatmap">{heatmap_html}</div>
  </section>

  <!-- Results Table -->
  <section>
    <h2>Technique Results</h2>
    <input class="search-bar" type="text" id="searchBox"
           placeholder="Search technique ID, name, tactic..."
           onkeyup="filterTable()">
    <div class="table-wrap">
      <table id="resultsTable">
        <thead>
          <tr>
            <th>ID</th><th>Name</th><th>Tactic</th><th>Status</th>
            <th>Confidence</th><th>Rules Hit</th><th>IOCs</th><th>Duration</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
  </section>

  <!-- Sigma Rules -->
  <section>
    <h2>Generated Sigma Rules ({len(sigma_rules)})</h2>
    <div class="sigma-grid">{sigma_html}</div>
  </section>

</main>

<footer>
  <p>
    Built with <span>PhantomWatch</span> · MITRE ATT&CK {meta.get("attack_version","v14")} ·
    Purple Team Automation by <span>Ahad</span>
  </p>
</footer>

<script>
  function filterTable() {{
    const q    = document.getElementById("searchBox").value.toLowerCase();
    const rows = document.querySelectorAll("#resultsTable tbody tr");
    rows.forEach(r => {{
      r.style.display = r.textContent.toLowerCase().includes(q) ? "" : "none";
    }});
  }}

  const BUNDLE_B64 = "{bundle_b64}";
  function downloadBundle() {{
    const blob = new Blob([atob(BUNDLE_B64)], {{type:"text/yaml"}});
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "phantomwatch_sigma_bundle.yml"; a.click();
    URL.revokeObjectURL(url);
  }}
</script>
</body>
</html>"""
