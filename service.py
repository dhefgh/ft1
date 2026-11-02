"""Background service: runs as an Android foreground service so checks continue
when the app is closed."""
import time

import core

last = 0
while True:
    cfg = core.load_cfg()
    if cfg.get("running"):
        interval = max(15, int(cfg.get("every") or 60)) * 60
        if time.time() - last >= interval:
            core.set_status(core.run_check(cfg))
            last = time.time()
    else:
        last = 0
    time.sleep(20)
