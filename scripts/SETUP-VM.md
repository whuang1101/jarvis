# VM setup for autonomous roadmap runs

Target: `learning-vm` (Ubuntu 24.04, azureuser). Node 22, gh CLI, Claude Code,
python3-venv are **already installed**. What remains needs interactive logins,
so it must be done by a human over SSH.

```bash
ssh learning-vm

# 1. GitHub auth (device flow — follow the browser prompt)
gh auth login            # choose GitHub.com, HTTPS, login with browser
gh auth setup-git

# 2. Claude auth (opens a login URL — use your Claude subscription account)
claude                   # complete login, then /exit

# 3. Clone + Python env
gh repo clone whuang1101/jarvis ~/jarvis
cd ~/jarvis
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest jarvis/tests -q    # expect: all passing

# 4. Smoke-test one supervised run (watch what it does the first time)
chmod +x scripts/improve-jarvis.sh
./scripts/improve-jarvis.sh &
tail -f ~/jarvis-improve.log

# 5. When you're happy with it, enable the cron loop
( crontab -l 2>/dev/null; echo "0 */5 * * * /home/azureuser/jarvis/scripts/improve-jarvis.sh" ) | crontab -
```

## Operating notes

- One roadmap step = one PR, squash-merged automatically when the test suite
  passes. Skim the merged PRs on GitHub to keep an eye on what changed.
- `~/jarvis-improve.log` on the VM has every run's transcript.
- The loop stops when Claude's quota runs dry and cron retries at the next
  5-hour boundary. Kick off `./scripts/improve-jarvis.sh` manually right after
  a quota reset once so the cron schedule aligns with your reset window.
- To pause everything: `crontab -r` on the VM.
- Optional: put your Azure OpenAI vars in `~/jarvis/.env` on the VM if you want
  the agent able to smoke-test the Jarvis REPL itself (`jarvis -p "2+2"`);
  tests don't need it.
