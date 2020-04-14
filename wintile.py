# dconf write /org/gnome/mutter/edge-tiling false

from contextlib import contextmanager
import Xlib
# Xlib.threaded is imported in order to make X11 communication thread safe
from Xlib import display, threaded
from Xlib.ext import record
from Xlib.protocol import rq
from threading import Thread, Lock
from sys import exit
from time import sleep
import os
from signal import SIGTERM
from tkinter import Tk, Label, Button


class WindowTileManager:
    def __init__(self):
        self.disp = display.Display()
        self.root = self.disp.screen().root
        self.NET_ACTIVE_WINDOW = self.disp.intern_atom('_NET_ACTIVE_WINDOW')

        # get display resolution
        self.WIDTH = self.root.get_geometry().width
        self.HEIGHT = self.root.get_geometry().height

        # maximum usable vertical dimension
        self.MAX_VERT = \
            self.root.get_full_property(
                self.disp.intern_atom('_NET_WORKAREA'),
                Xlib.X.AnyPropertyType)._data['value'][1][3]

        # set actuation border width
        self.ACTIVE_BORDER = 70

        # needed data of the last focused window, initialize lock.
        self.last_focused = {'id': None, 'root_x': -1, 'root_y': -1, 'moved': False}
        self.mutex = Lock()

        # main loop condition variable
        self.run = True

        # self.root.change_attributes(
        #     event_mask=Xlib.X.StructureNotifyMask)

    # mange window objects creation via win id, return win object or none on failure.
    # dismiss any Xlib.erros when trying to acquire window object
    @contextmanager
    def get_win_object(self, win_id):
        # __enter__
        win_obj = None
        if win_id:
            try:
                win_obj = self.disp.create_resource_object('window', win_id)
            except Xlib.error.XError:
                pass
        # with - as
        yield win_obj
        # __exit__

    # compare current active window to the last focused window.
    # return the current window id and state change bool
    def get_active_window(self):
        win_id = self.root.get_full_property(self.NET_ACTIVE_WINDOW,
                                             Xlib.X.AnyPropertyType).value[0]
        if win_id == 0:
            return
        changed_focus = (win_id != self.last_focused['id'])
        if changed_focus:
            with self.get_win_object(self.last_focused['id']) as previous_win:
                # remove event mask from prev window. no events notification are needed.
                if previous_win and previous_win != self.root:
                    previous_win.change_attributes(event_mask=Xlib.X.NoEventMask)
            pointer_data = display.Display().screen().root.query_pointer()._data

            # update window data
            self.mutex.acquire()
            try:
                self.last_focused['root_x'] = pointer_data['root_x']
                self.last_focused['root_y'] = pointer_data['root_y']
                self.last_focused['id'] = win_id
                self.last_focused['moved'] = False
            finally:
                self.mutex.release()

            # set event mask on newly focused window
            with self.get_win_object(win_id) as current_win:
                if current_win and current_win != self.root:
                    current_win.change_attributes(
                        event_mask=Xlib.X.StructureNotifyMask)
        return win_id, changed_focus

    # handle window dragging
    def _handle_xevent(self, event):
        # abort on window closure
        if event.type == Xlib.X.DestroyNotify:
            return
        # window's properties changed event
        elif event.type == Xlib.X.ConfigureNotify:
            pointer = display.Display().screen().root.query_pointer()._data
            self.mutex.acquire()
            try:
                # check if pointer is pressed and moving, if so, update data.
                self.last_focused['moved'] = pointer['mask'] & Xlib.X.Button1MotionMask
                if self.last_focused['moved']:
                    self.last_focused['root_x'] = pointer['root_x']
                    self.last_focused['root_y'] = pointer['root_y']
            finally:
                self.mutex.release()
        else:
            pass
        self.get_active_window()

    def move_win(self, root_x, root_y, win_id):
        move = False

        # get display parameters
        HEIGHT = self.HEIGHT
        WIDTH = self.WIDTH
        ACTIVE_BORDER = self.ACTIVE_BORDER

        # bottom edge
        if root_y > HEIGHT - ACTIVE_BORDER:

            # left third
            if root_x < WIDTH / 3:
                x = 0
                w = int(WIDTH / 3)
                move = True

            # middle third
            elif WIDTH / 3 < root_x < 2 * WIDTH / 3:
                x = int(WIDTH / 3)
                w = int(WIDTH / 3)
                move = True

            # right third
            elif 2 * WIDTH / 3 < root_x:
                x = int(2 * WIDTH / 3)
                w = int(WIDTH / 3)
                move = True

        elif HEIGHT / 3 < root_y < 2 * HEIGHT / 3:
            # left middle edge
            if root_x < ACTIVE_BORDER:
                x = 0
                w = int(WIDTH / 2)
                move = True
            # right middle edge
            elif root_x > WIDTH - ACTIVE_BORDER:
                x = int(WIDTH / 2)
                w = int(WIDTH / 2)
                move = True

        # top edge
        elif root_y < ACTIVE_BORDER:

            # left top corner
            if root_x < ACTIVE_BORDER:
                x = 0
                w = int(2 * WIDTH / 3)
                move = True

            # right top corner
            if root_x > WIDTH - ACTIVE_BORDER:
                x = int(WIDTH / 3)
                w = int(2 * WIDTH / 3)
                move = True

            # middle top third edge
            if int(WIDTH / 3) < root_x < int(2 * WIDTH / 3):
                x = int(WIDTH * 0.15)
                w = int(WIDTH * 0.7)
                move = True

        if move:
            win = self.disp.create_resource_object('window', win_id)
            win.unmap()
            win.map()
            win.configure(x=x, y=0, width=w, height=self.MAX_VERT)
            self.disp.sync()

    # listen to the given file descriptor
    # to be used as Thread.run()
    def __mouse_listener(self, fd):
        read = os.fdopen(fd)
        while True:
            line = read.readline()
            if 'released' in line:
                # mouse button1 released
                self.mutex.acquire()
                try:
                    moved = self.last_focused['moved']
                    root_x = self.last_focused['root_x']
                    root_y = self.last_focused['root_y']
                    win_id = self.last_focused['id']
                finally:
                    self.mutex.release()
                if moved:
                    # moved and mouse released = window dragged -> move_win if needed
                    self.move_win(root_x, root_y, win_id)

    class _MouseRecord:
        # to be called with new xlib event
        def __mouse_listener(self, reply):
            data = reply.data
            while len(data):
                event, data = rq.EventField(None).parse_binary_value(data, self._disp.display, None, None)
                if event.detail == self.BUTTON1 and event.type == Xlib.X.ButtonRelease:
                    os.write(self.STDOUT, b"released\n")

        def __init__(self):
            self._disp = Xlib.display.Display()
            self.BUTTON1 = 1
            self.STDOUT = 1

            self.__rec_context = self._disp.record_create_context(
                0,
                [record.AllClients],
                [{
                    'core_requests': (0, 0),
                    'core_replies': (0, 0),
                    'ext_requests': (0, 0, 0, 0),
                    'ext_replies': (0, 0, 0, 0),
                    'delivered_events': (0, 0),
                    'device_events': (Xlib.X.ButtonPressMask, Xlib.X.ButtonReleaseMask),
                    'errors': (0, 0),
                    'client_started': False,
                    'client_died': False,
                }])
            self._disp.record_enable_context(self.__rec_context, self.__mouse_listener)
            self._disp.record_free_context(self.__rec_context)

    def start(self):
        STDIN = 0
        STDOUT = 1
        STDERR = 2
        read_fd, write_fd = os.pipe()

        # open child process which runs ms_req.py
        pid = os.fork()
        if pid < 0:
            print('fork error')
            exit(1)
        # child - run a mouse event recorder in a new process.
        # event handling must be separated. otherwise the mouse events shadows win events.
        elif pid == 0:
            os.close(read_fd)
            os.dup2(write_fd, STDOUT)
            os.dup2(write_fd, STDERR)
            # os.execl('/usr/bin/python3', '/usr/bin/python3', 'ms_req.py')
            # print('execl failed')
            # exit(2)
            self._MouseRecord()
        # parent - run window event handler
        os.close(write_fd)
        self.root.change_attributes(event_mask=Xlib.X.PropertyChangeMask)
        self.get_active_window()

        # create new daemon threads (to avoid busy waiting)
        # mouse listener-   listens to the given file descriptor.
        #                   in this case, the piped output of the mouse event listener.
        # terminator    -   GUI based thread, waits user input to terminate the program
        t_mouse_listener = Thread(target=self.__mouse_listener, args=(read_fd,))
        t_terminate = Thread(target=self.__terminate, args=())
        t_terminate.daemon = t_mouse_listener.daemon = True
        t_terminate.start()
        t_mouse_listener.start()
        while self.run:
            # next_event blocks until new requested event
            self._handle_xevent(self.disp.next_event())
        os.kill(pid, SIGTERM)

    class UI:
        def __init__(self, root):
            self.root = root
            self.root.geometry("200x70")
            root.title("Wintile")
            root.resizable(False, False)
            self.label = Label(root, text="Drag desired window\n to tile it into position.")
            self.label.pack()
            self.close_button = Button(root, text="Close", command=root.quit)
            self.close_button.pack()

    # terminate program on GUI exit
    # to be used as Thread.run()
    def __terminate(self):
        root = Tk()
        # root.wm_state('iconic')
        # root.iconify()
        self.UI(root)
        root.mainloop()
        self.run = False
        # send dummy event, to unblock next_event thread.
        win = self.disp.create_resource_object('window', self.get_active_window()[0])
        win.configure(height=win.get_geometry().height)
        self.disp.sync()
        exit(0)


def main():
    win_tiling_manger = WindowTileManager()
    win_tiling_manger.start()


if __name__ == '__main__':
    main()
