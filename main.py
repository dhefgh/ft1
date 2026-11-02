from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.utils import platform

import core

FIELDS = [
    ("origin", "Origin airport code (e.g. ACC)", False),
    ("dest", "Destination airport code (e.g. LHR)", False),
    ("depart", "Departure date YYYY-MM-DD", False),
    ("ret", "Return date YYYY-MM-DD (blank = one-way)", False),
    ("adults", "Passengers", False),
    ("currency", "Currency (USD, EUR, GHS...)", False),
    ("target", "Alert when price at or below", False),
    ("every", "Check every N minutes (min 15)", False),
    ("key", "Amadeus API key", False),
    ("secret", "Amadeus API secret", True),
    ("env", "API environment: test or production", False),
    ("ntfy", "ntfy topic (optional)", False),
]


class FareApp(App):
    def build(self):
        self.title = "Fare Tracker"
        cfg = core.load_cfg()
        root = BoxLayout(orientation="vertical", padding=10, spacing=6)

        form = BoxLayout(orientation="vertical", size_hint_y=None, spacing=4)
        form.bind(minimum_height=form.setter("height"))
        self.inputs = {}
        for key, hint, pw in FIELDS:
            ti = TextInput(text=str(cfg.get(key, "")), hint_text=hint, multiline=False,
                           password=pw, size_hint_y=None, height=96)
            self.inputs[key] = ti
            form.add_widget(ti)
        sv = ScrollView(size_hint_y=0.5)
        sv.add_widget(form)
        root.add_widget(sv)

        row = BoxLayout(size_hint_y=None, height=110, spacing=6)
        row.add_widget(Button(text="Save & Start", on_press=self.start))
        row.add_widget(Button(text="Stop", on_press=self.stop))
        row.add_widget(Button(text="Check now", on_press=self.check_now))
        root.add_widget(row)

        self.status = Label(text=core.get_status(), size_hint_y=None, height=120,
                            text_size=(None, None))
        self.status.bind(width=lambda w, v: setattr(w, "text_size", (v, None)))
        root.add_widget(self.status)

        self.hist = Label(text="", valign="top")
        self.hist.bind(size=lambda w, s: setattr(w, "text_size", s))
        root.add_widget(self.hist)

        Clock.schedule_interval(self.refresh, 5)
        self.refresh()
        if platform == "android":
            self.ask_permissions()
        return root

    def ask_permissions(self):
        try:
            from android.permissions import request_permissions
            request_permissions(["android.permission.POST_NOTIFICATIONS"])
        except Exception:
            pass

    def read_cfg(self):
        return {k: v.text.strip() for k, v in self.inputs.items()}

    def start(self, *_):
        cfg = self.read_cfg()
        if not (cfg["origin"] and cfg["dest"] and cfg["depart"] and cfg["key"] and cfg["secret"]):
            self.status.text = "Fill in origin, destination, departure date, API key and secret."
            return
        cfg["running"] = True
        core.save_cfg(cfg)
        core.set_status("Started. First check running...")
        if platform == "android":
            self.service_ctl(True)
        self.status.text = core.get_status()

    def stop(self, *_):
        cfg = core.load_cfg()
        cfg["running"] = False
        core.save_cfg(cfg)
        if platform == "android":
            self.service_ctl(False)
        core.set_status("Stopped.")
        self.status.text = core.get_status()

    def check_now(self, *_):
        cfg = self.read_cfg()
        core.save_cfg({**cfg, "running": core.load_cfg().get("running", False)})
        self.status.text = "Checking..."
        import threading

        def work():
            msg = core.run_check(cfg)
            core.set_status(msg)
        threading.Thread(target=work, daemon=True).start()

    def service_ctl(self, on):
        try:
            from android import mActivity
            from jnius import autoclass
            name = "org.fares.faretracker.ServiceFares"
            svc = autoclass(name)
            if on:
                svc.start(mActivity, "")
            else:
                Intent = autoclass("android.content.Intent")
                mActivity.stopService(Intent(mActivity, svc))
        except Exception as e:
            core.set_status(f"Service error: {e}")

    def refresh(self, *_):
        self.status.text = core.get_status()
        rows = core.history(10)
        self.hist.text = "\n".join(
            f"{r[0][5:16].replace('T', ' ')}  {r[2]:.0f}  {r[3]}  {r[4]} stop(s)" for r in rows
        ) or "No price history yet."


if __name__ == "__main__":
    FareApp().run()
