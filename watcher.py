from datetime import datetime
from logger import log
from threading import Event, Timer
from typing import List

import pyinotify

last_update = datetime.now()
UPDATE_DIFF_IN_SEC = 2

class Watcher:
    def __init__(self, stop_event: Event, onupdate, directories: List[str]) -> None:
        self.stop_event = stop_event
        self.onupdate = onupdate
        self.directories = directories
    
    def start(self):
        # Watch manager
        wm = pyinotify.WatchManager()
        
        # Notifier using the built EventHandler and reading 10ms intervals
        notifier = pyinotify.Notifier(wm, EventHandler(onupdate=self.onupdate), timeout=1)
        
        for watch_dir in self.directories:
            # Add a recursive watch
            wm.add_watch(watch_dir, pyinotify.ALL_EVENTS, rec=True)

            log(f"Watching directory: {watch_dir}")
            
        while not self.stop_event.is_set():
            try:
                notifier.process_events()
                if notifier.check_events():
                    notifier.read_events()
            except pyinotify.NotifierError:
                pass
        notifier.stop()


def try_to_update_repo(onupdate):
    global last_update, UPDATE_DIFF_IN_SEC
    now = datetime.now()

    time_diff = (now - last_update).total_seconds()
    
    if time_diff >= UPDATE_DIFF_IN_SEC:
        last_update = now
        t = Timer(0.5, onupdate)
        t.start()


class EventHandler(pyinotify.ProcessEvent):
    def __init__(self, pevent=None, **kargs):
        self.onupdate = kargs["onupdate"]
        super().__init__(pevent, **kargs)

    def process_IN_ACCESS(self, event):
        pass

    def process_IN_ATTRIB(self, event):
        pass

    def process_IN_CLOSE_NOWRITE(self, event):
        pass

    def process_IN_CLOSE_WRITE(self, event):
        pass

    def process_IN_CREATE(self, event):
        log(f"CREATE: {event.pathname}")
        try_to_update_repo(self.onupdate)

    def process_IN_DELETE(self, event):
        log(f"DELETE: {event.pathname}")
        try_to_update_repo(self.onupdate)

    def process_IN_MODIFY(self, event):
        log(f"MODIFY: {event.pathname}")
        try_to_update_repo(self.onupdate)

    def process_IN_OPEN(self, event):
        pass
    
    def process_IN_MOVED_FROM(self, event):
        log(f"MOVED_FROM: {event.pathname}")
        try_to_update_repo(self.onupdate)
    
    def process_IN_MOVED_TO(self, event):
        log(f"MOVED_TO: {event.pathname}")
        try_to_update_repo(self.onupdate)
    
    def process_default(self, event):
        pass