import subprocess

def run(cmd):
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return f"CMD: {cmd}\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}\nEXIT CODE: {res.returncode}\n{'-'*50}\n"
    except Exception as e:
        return f"CMD: {cmd}\nERROR: {e}\n{'-'*50}\n"

with open("git_output.txt", "w") as f:
    f.write(run("git status"))
    f.write(run("git rm --cached scholaris.db first.py fix_runner.py upgrade_to_admin.py cleanup.py migrations/ instance/ -r"))
    f.write(run("git add ."))
    f.write(run("git commit -m \"feat: simplify database to flat JSON file storage and clean requirements\""))
    f.write(run("git log -n 1"))
    f.write(run("git remote -v"))
