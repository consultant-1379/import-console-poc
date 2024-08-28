import inspect
import re
import os
import fnmatch
import sys
import uibind_worker
import time

import urwid as u
import logging

logger = logging.getLogger(__name__)

output = ''

catch_view_exceptions = True


def disable_catch_view_exceptions():
    global catch_view_exceptions
    catch_view_exceptions = False


class Display(object):
    """
    View management class that coordinates the displaying of views
    and dispatching some keyboard events
    """
    def __init__(self, palette=[], style=None):
        """
        :param palette: color palette to be used
        :param style: default style to be applied on the views
        """
        self._style = style
        self._palette = palette
        self._app_area = None
        self._started = False
        self._view_stack = []
        self._transitioning = False
        self._transition_error = None
        self.exception_handler = None
        self._loop = None
        self._alarm_handle = None
        self._worker = uibind_worker.Worker()
        self._update_interval = 30
        self._is_first_alarm = True

    def handle_input(self, key):
        """
        Method called whenever there is an unhandled key-stroke.
        It forwards the key to the current view.
        :param key: key pressed by the user
        :return: None
        """
        if len(self._view_stack) > 0:
            self._view_stack[-1].handle_input(key)

    def handle_exception(self, e):
        """
        Method called whenever an exception is thrown by a View.
        Current implementation forwards the exception to the registered exception_handler. If there is no
        exception handler, then the exception is raised.
        :param e: the exception
        :return: None
        """
        if self._transitioning:
            self._transition_error = e
            return

        self._transition_error = None
        if callable(self.exception_handler):
            self.exception_handler(e, self._view_stack[-1] if len(self._view_stack) > 0 else None)
        else:
            raise e

    def set_update_interval(self, interval_seconds):
        self._update_interval = interval_seconds

    def start(self, view):
        """
        Starts the UI display.
        This method will block until the UI is destroyed.
        :param view: the view to be shown at start.
        :return: None
        """
        if self._started:
            raise RuntimeError

        ui_widget = None
        try:
            self._transitioning = True
            view.set_display(self)
            view._before_build()
            if not self._transition_error:
                ui_widget = view.build_ui()
            if not self._transition_error:
                self._view_stack.append(view)
                view._after_build()
        except BaseException as e:
            view.set_display(None)
            if not self._transition_error:
                self._transition_error = e
        finally:
            self._transitioning = False
            if self._transition_error:
                view.set_display(None)
                self.handle_exception(self._transition_error)
                return
        if self._style:
            ui_widget = u.AttrMap(ui_widget, self._style)
        self._app_area = u.WidgetPlaceholder(ui_widget)

        loop = u.MainLoop(self._app_area, palette=self._palette, pop_ups=True, unhandled_input=self.handle_input)
        loop.screen.set_terminal_properties(colors=256)
        self._loop = loop
        self._set_next_alarm()
        self._started = True
        view._after_show()
        loop.run()

    def show_view(self, view):
        """
        Changes the current view to he provided one.
        :param view: the view to be displayed
        :return: None
        """
        try:
            self._transitioning = True
            view.set_display(self)
            view._before_build()
            ui = None
            if not self._transition_error:
                ui = view.build_ui()
            if not self._transition_error:
                view._after_build()
            if not self._transition_error:
                if len(self._view_stack) == 0 or self._view_stack[-1] != view:
                    self._view_stack.append(view)
            if not self._transition_error:
                self._app_area.original_widget = ui
                view._after_show()
        finally:
            self._transitioning = False
            if self._transition_error:
                self.handle_exception(self._transition_error)

    def back(self):
        """
        Move back to the previous view.
        If there is no view to move back to, the Display is ended.
        :return:
        """
        if len(self._view_stack) <= 1:
            raise u.ExitMainLoop()
        try:
            self._transitioning = True
            self._view_stack.pop()
            prev = self._view_stack[-1]
            self._app_area.original_widget = prev.get_ui_element()
            prev._after_show()
        finally:
            self._transitioning = False
            if self._transition_error:
                self.handle_exception(self._transition_error)

    def rebuild_ui(self):
        """
        Forces the current View to rebuild itself.
        :return: None
        """
        if len(self._view_stack) > 0:
            try:
                self._transitioning = True
                view = self._view_stack[-1]
                ui = view.build_ui()
                if not self._transition_error:
                    self._app_area.original_widget = ui
            finally:
                self._transitioning = False
                if self._transition_error:
                    self.handle_exception(self._transition_error)

    def redraw_ui(self):
        """
        Forces the screen to be re-drawn.
        Should be used only when a UI element was changed by an external Thread.
        :return: None
        """
        self._loop.draw_screen()

    def request_work(self, call):
        """
        Sends a work to be executed by a background thread. The worker only executes the latest work submitted, hence
        there is no guarantee that the work will ever be done.

        :param call: callable to be executed
        :return: a work id that can be used to interrogate the worker about the status of the submitted work.
        """
        return self._worker.request(call)

    def get_work(self, work_id):
        """
        Try to fetch the status of the work associated with the given work-id.
        :param work_id: id of the work previously submitted with request_work(callable)
        :return: a Work object or None if the work associated with the given Id has been discarded
        """
        return self._worker.get_work_for(work_id)

    def _on_alarm_fired(self, loop, data):
        try:
            if len(self._view_stack) > 0:
                self._view_stack[-1].update_interval()
        finally:
            self._set_next_alarm()

    def _fix_ui(self, loop, data):
        # workaround a glitch on the web-terminal where some of the color code is not interpreted correctly on the
        # first screen
        loop.screen.clear()
        self._set_next_alarm()

    def _set_next_alarm(self):
        if self._alarm_handle:
            self._loop.remove_alarm(self._alarm_handle)
        if self._is_first_alarm:
            self._is_first_alarm = False
            self._alarm_handle = self._loop.set_alarm_in(.1, self._fix_ui)
        else:
            self._alarm_handle = self._loop.set_alarm_in(self._update_interval, self._on_alarm_fired) if self._update_interval > 0 else None


class ViewMeta(type):
    """
    Class meta used by all views in order to add error handling support.
    """
    def __new__(cls, *args, **kwargs):
        instance = type.__new__(cls, *args, **kwargs)
        methods = inspect.getmembers(instance, predicate=inspect.ismethod)
        wrapped = {}
        for n, m in methods:
            if n.startswith('__') or hasattr(m, 'is_error_wrapper') or hasattr(m, 'is_skip_error_wrapper'):
                continue
            delegate = cls.wrap_with_delegate(m)
            setattr(instance, n, delegate)
            wrapped[n] = delegate

        # updating uibindinds
        for name, func in methods:
            if hasattr(func, 'uibind'):
                if callable(func.uibind.source):
                    func.uibind.source = wrapped.get(func.uibind.source.__name__, func.uibind.source)
                if callable(func.uibind.value):
                    func.uibind.value = wrapped.get(func.uibind.value.__name__, func.uibind.value)
                if callable(func.uibind.element_bind):
                    func.uibind.element_bind = wrapped.get(func.uibind.element_bind.__name__, func.uibind.element_bind)

        return instance

    @staticmethod
    def wrap_with_delegate(func):
        def _delegate_wrap(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            except u.ExitMainLoop:
                raise
            except BaseException as e:
                if not catch_view_exceptions:
                    info = sys.exc_info()
                    raise info[0], info[1], info[2]
                if self.get_display():
                    self.get_display().handle_exception(e)
                else:
                    info = sys.exc_info()
                    raise info[0], info[1], info[2]
        for name, method in inspect.getmembers(func):
            if not name.startswith('__'):
                setattr(_delegate_wrap, name, method)
        _delegate_wrap.is_error_wrapper = True
        _delegate_wrap.__name__ = func.__name__
        return _delegate_wrap


class View(object):
    """Base class for UI generation and binding"""

    __metaclass__ = ViewMeta

    def __init__(self, title='', style=None, align='center', valign='top', width=('relative', 100), left=3, right=3, height=('relative', 100), top=1, bottom=1):
        """
        :param title: view title to be displayed at the top
        :param style: color style to be applied to the view. Expected to be a tuple with 2 elements being pallet entry
        names like ('style_name', 'focus_style_name')
        :param align: horizontal alignment of the view
        :param valign: vertical alignment of the view
        :param width: view width in columns number. Can be a fixed number like '10' or relative like ('relative', 100)
        :param left: fixed number of padding columns
        :param right: fixed number of padding columns
        :param height: fixed number of padding columns
        :param top: fixed number of padding columns
        :param bottom: fixed number of padding columns
        """
        self._style = style
        self._width = width
        self._bottom = bottom
        self._top = top
        self._height = height
        self._right = right
        self._left = left
        self._valign = valign
        self._align = align
        self._display = None
        self._element = None
        self._value = None
        self._title = title
        self._shortcut = {}

    def set_display(self, display):
        """
        Sets the associated Display to this view.
        :param display: a Display instance
        :return: None
        """
        self._display = display

    def get_display(self):
        """
        Returns the associated display to this view.
        :return: A instance of Display
        """
        return self._display

    def get_ui_element(self):
        """
        Gets the root UI element of this view.
        :return: a widget element with is the root of this view
        """
        return self._element

    def get_value(self):
        """
        returns the current value associated with this view
        :return: any object as the view value
        """
        return self._value

    def set_value(self, value):
        """
        Sets the current value associated to this view
        :param value: any value object
        :return: None
        """
        self._value = value

    def build_ui(self):
        """
        Builds all the UI elements.
        :return: the top root widget
        """
        content = self._build_content()
        if self._style:
            content = u.AttrMap(content, *self._style)

        horizontal_pos = u.Padding(content, align=self._align, left=self._left, right=self._right, width=self._width)
        top = u.Filler(horizontal_pos, valign=self._valign, height=self._height, top=self._top, bottom=self._bottom)

        self._element = top
        return self._element

    def _build_content(self):
        widgets = []
        for method in [m for n, m in inspect.getmembers(self, predicate=inspect.ismethod)]:
            if hasattr(method, "uibind"):
                binder = getattr(method, "uibind")
                widget = binder.build(self)
                if widget:
                    if binder.size is None:
                        element = widget
                    elif isinstance(binder.size, (list, tuple)):
                        element = (binder.size[0], binder.size[1], widget)
                    else:
                        element = (binder.size, widget)

                    widgets.append((element, binder.order or 0))

        widgets.sort(key=lambda item: item[1])
        window = u.LineBox(u.Padding(u.Pile([w for w, o in widgets if w]), left=2, right=2), self._title)

        return window

    def get_value_of(self, key_view_element):
        """
        Gets the value of the given UI element
        :param key_view_element: usually a method of the view which is bound to a UI element
        :return: the value
        """
        ui = backing_ui(self)
        if ui is None:
            return None
        return ui.get_value(key_view_element)

    def get_element_of(self, key_view_element):
        """
        Gets the UI element (widget) associated to the given element key.
        :param key_view_element: usually a method of the view which is bound to a UI element
        :return: a UI element (widget)
        """
        ui = backing_ui(self)
        if ui is None:
            return None
        return ui.get_element(key_view_element)

    def before_build(self):
        """
        Lifecycle method called before the view is asked to build itself.
        Should be used in case any preparation is needed before building the view.
        :return: None
        """
        pass

    def after_build(self):
        """
        Lifecycle method called after the view has built itself.
        :return: None
        """
        pass

    def after_show(self):
        """
        Lifecycle method called after the view has been displayed
        :return: None
        """
        pass

    def update_interval(self):
        """
        Method called in a regular interval. Views can overwrite this method
        to execute recurring tasks like, updating information.
        :return: None
        """
        pass

    def _before_build(self):
        self.before_build()

    def _after_build(self):
        self.after_build()

    def _after_show(self):
        self.after_show()

    def register_shortcut(self, key, action, target, args):
        """
        Register a action on a ui-element to be triggered upon a user keyboard input.
        Eg.:
            self.register_shortcut('enter', 'keypress', self.get_element_of(self.buttons)[0], (None, 'enter'))

        :param key: key pressed by the user which will trigger this shortcut
        :param action: the action to be triggered on the target element
        :param target: the target ui element (widget) which will be triggered
        :param args: arguments to be passed to the ui-element's action handler
        :return: None
        """
        self._shortcut[key] = (action, target, args)

    def handle_input(self, key):
        """
        This method is invoked by the Display whenever there is an unhandled user input.
        The default behaviour is to trigger a registered shortcut
        :param key:
        :return:
        """
        shortcut = self._shortcut.get(key, None)
        if shortcut:
            action, target, args = shortcut
            to_call = getattr(target, action)
            if args:
                to_call(*args)
            else:
                to_call()

    def show_popup(self, popup_view):
        """
        Helper method that allows a unbinded PopUp to be displayed.
        :param popup_view: Instance of PopupView to be displayed
        :return: None
        """

        def mock_holder(view_instance):
            return popup_view

        holder = popup()(mock_holder)
        holder.uibind.build(self)
        holder.popup.show()


class PopUpViewMeta(u.signals.MetaSignals, ViewMeta):
    """
    Class metada to be applied on all popup views
    """
    pass


class PopUpView(View):
    """
    Base class for building popup like views.
    """
    __metaclass__ = PopUpViewMeta

    signals = ['close_popup']

    def __init__(self, title='', style=None, align='center', valign='middle', width=('relative', 60), left=3, right=3,
                 height=('relative', 60), top=1, bottom=1):
        super(PopUpView, self).__init__(title, style, align, valign, width, left, right, height, top, bottom)

    def build_ui(self):
        content = self._build_content()
        if self._style:
            content = u.AttrMap(content, *self._style)

        popup = u.Overlay(content,
                          u.SolidFill(u'\N{LIGHT SHADE}'),
                          align=self._align, width=self._width,
                          valign=self._valign, height=self._height,
                          top=self._top, bottom=self._bottom,
                          left=self._left, right=self._right,
                          min_width=20, min_height=9)

        self._element = popup
        return self._element

    def close(self):
        """
        Close the popup.
        :return: None
        """
        u.emit_signal(self, 'close_popup', self, self.get_value())


def textinput(caption='', size='pack', order=None, style=None, action_on_enter=True, disable_on_none=False):
    """
    Decorator that produces a text input.

    if the decorated function returns a String that string will be used as the input initial value.

    if the decorated function returns None and the option disable_on_none is set to True, then the input will
    not be constructed at all.

    A change listener can be defined by using the listener decorator as in::

            @uibind.textinput()
            def func1(self):
                pass

            @func1.uibind.listener
            def func1_listener(self, obj, value):
                pass

    :element-value: edit box's text contents
    :param caption: Text to be shown before the user input.
    :param size: one of
                'pack' - minimum size
                number - a integer of the required size
                tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
                  names like ('style_name', 'focus_style_name').
    :param action_on_enter: whether or not the enter key should trigger a event with the value 'enter'. If false
                            pressing enter does not trigger an event
    :param disable_on_none: If true, when the binding function returns None the element will NOT be created.
    :return: decorator function
    """
    def bind(source_func):
        binder = Binder(source_func)
        fill = False if size else True
        binder.builder = TextInputBuilder(caption, style=style, action_on_enter=action_on_enter, fill_bottom=fill, disable_on_none=disable_on_none)
        binder.size = size
        binder.order = order
        source_func.uibind = binder
        return source_func
    return bind


def listbox(item_builder, buffer_size=100, size='pack', order=None, style=None):
    """
    Decorator that produces a listbox.

    The decorated function is expected to return a list of Strings or an implementation of NavigableDataSource. if
    anything else is returned, it will converted to String and put in a single element list.

    if the decorated function returns None then the input will not be constructed at all.

    :element-value: the selected item of the list
    :param item_builder: builder (uibind.WidgetBuilder extension) which is called to build ui-elements for each line
                        of the list.
    :param buffer_size: number of elements to fetch from the datasource and keep it in memory.
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
                 names like ('style_name', 'focus_style_name')
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        binder.builder = ListBuilder(item_builder, buffer_size, style=style)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def filebrowser(root_path=None, size=None, order=None, style=None, item_style=None, item_order_by=None, show_files=True):
    """
    Decorator that produces a tree-list listing a file-system directory content.

    if the root_path parameter is passed then the wrapped function return value is ignored. Otherwise, it's expected
    of the function's return value to be a String pointing to the start path of the tree-list or None. In the later case
    the element will not be constructed at all.

    :element-value: String with the selected path
    :param root_path: start path of the tree-list
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
                    names like ('style_name', 'focus_style_name')
    :param item_style: color style to be applied to each element on the list. Expected to be a tuple with 2 elements being pallet entry
                    names like ('style_name', 'focus_style_name')
    :param item_order_by: specifies a function of one argument that is used to extract a comparison key from each list element
    :param show_files: if true the list will also show files
    :return: decorator function
    """
    def bind(func):
        if root_path:
            binder = Binder(root_path, element_bind=func)
        else:
            binder = Binder(func)
        binder.builder = FileBrowserBuilder(style=style, item_style=item_style, item_order_by=item_order_by, show_files=show_files)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def text(align='left', wrap='space', size='pack', order=None, style=None, valign='top'):
    """
    Decorator that produces a text element.

    The decorated function is expected to return the text to be displayed.

    if the decorated function returns None, then the text element will not be constructed at all.

    :element-value: the text string
    :param align: text horizontal alignment 'left', 'center' or 'right'
    :param wrap: text wrapping mode - typically 'space', 'any' or 'clip'
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
            names like ('style_name', 'focus_style_name')
    :param valign: text vertical alignment 'top', 'middle' or 'bottom'
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        fill = False if size else True
        binder.builder = TextBuilder(align=align, wrap=wrap, style=style, fill_bottom=fill, valign=valign)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def progressbar(align='left', valign='top', style_normal=None, style_complete=None, style_satt=None, done_at=100, width=u.RELATIVE_100, size='pack', order=None):
    """
    Decorator that produces a progress bar element.

    The decorated function is expected to return the current progress or a tuple with as (max_value, current_value).

    if the decorated function returns None, then the element will not be constructed at all.

    :element-value: the current progress
    :param done_at: the maximum value representing 100%
    :param align: text horizontal alignment 'left', 'center' or 'right'
    :param width: one of:
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('relative', 100)
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style_normal: name of color style to be applied to the normal part of the progress element.
    :param style_complete: name of color style to be applied to the complete part of the progress element.
    :param style_satt: name of color style for smoothed part of bar where the foreground of satt corresponds to the normal part and the background corresponds to the complete part. If satt is None then no smoothing will be done.
    :param valign: text vertical alignment 'top', 'middle' or 'bottom'
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        fill = False if size else True
        binder.builder = ProgressBarBuilder(align=align, valign=valign, style_normal=style_normal, style_complete=style_complete, style_satt=style_satt, done_at=done_at, fill_bottom=fill, width=width)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def texttable(align='left', size='pack', col_sizes=None, order=None, style=None):
    """
    Decorator that produces a column separated list of text.

    The decorated function is expected to return one of:
        - Implementation of NavigableDataSource where each item is a list of strings.
        - list of lists of string.
        - None

    if the decorated function returns None, then the list element will not be constructed at all.

    :element-value: the list element of the focused row
    :param align: text horizontal alignment for the cells 'left', 'center' or 'right'. It can be a text in which case
         all the cells will have the same alignment or a list specifying the alignment for each column.
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param col_sizes: same as size, but applied to the text element in each column. This property also support specifying
            a list containing the size specification for each column.
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
            names like ('style_name', 'focus_style_name'). This property also support specifying a list containing the style
            specification for each column.
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        binder.builder = TextTableBuilder(align=align, style=style, col_sizes=col_sizes)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def divider(char=u' ', top=0, bottom=0, size='pack', order=None, style=None):
    """
    Decorator that produces a horizontal divider line.

    if the char parameter is passed then the wrapped function return value is ignored. Otherwise, it's expected
    of the function's return value to be a String with the separator char to be used or None. In the later case
    the element will not be constructed at all.

    :param char: character to be used as divider. Default to spaces
    :param top: fixed number of spaces above the divider
    :param bottom: fixed number of spaces below the divider
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
        names like ('style_name', 'focus_style_name')
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        binder.builder = DividerBuilder(char=char, top=top, bottom=bottom, style=style)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def buttons(labels=None, align='right', size='pack', order=None, style=None):
    """
    Decorator that produces one or more buttons horizontally aligned to each other.

    if the labels parameter is passed then the wrapped function is assumed to be the action listener of the buttons.
    Otherwise, it's expected of the function's return value to be a String or a list of strings of the button label(s)
    or None. In the later case the element will not be constructed at all.

    To register an action listener when the labels attribute is NOT provided it is required to use the uibind.listener
    decorator. Example::

            @uibind.buttons()
            def func1(self):
                return '[O]k'

            @func1.uibind.listener
            def func1_listener(self, obj, value):
                pass

    if a button label contains one character within square brackets, then this character will be registered as shortcut
    to activate the respective button.

    :param labels: optional list of button labels. There will be one button created for each label
    :param align: horizontal alignment of the buttons 'left', 'center' or 'right'
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
        names like ('style_name', 'focus_style_name')
    :return: decorator function
    """
    def bind(func):
        if labels:
            binder = Binder(labels, func)
        else:
            binder = Binder(func)
        fill = False if size else True
        binder.builder = ButtonBuilder(style=style, align=align, fill_bottom=fill)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def radios(group=None, labels=None, align='right', size='pack', order=None, style=None, caption=None, caption_style=None):
    """
    Decorator that produces one or more radio buttons horizontally aligned to each other.

    if the labels parameter is passed then the wrapped function is assumed to be the action listener of the buttons.
    Otherwise, it's expected of the function's return value to be one of:
        - a String : which will drive the creation of one radio button
        - a list of strings : each string will be one radio button and they will all belong to the same group
        - a list of list of strings : similar to above, but each list will be considered as a different group
        - None : the element will not be constructed at all.

    To register an action listener when the labels attribute is NOT provided it is required to use the uibind.listener
    decorator. Example::

            @uibind.radios()
            def func1(self):
                return '[O]k'

            @func1.uibind.listener
            def func1_listener(self, obj, value, label):  # value is either True or False
                pass


    :element-value: list containing the label of the selected element of each group
    :param group: optionally set a list tha will be used as the logical grouping of the radios.
    :param labels: optional list of radio button labels. There will be one radio button created for each label
    :param align: horizontal alignment of the buttons 'left', 'center' or 'right'
    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
        names like ('style_name', 'focus_style_name')
    :param caption: optionally set a caption which will be shown on the left of the radio buttons
    :param caption_style: set the style to be used on the caption
    :return: decorator function
    """
    def bind(func):
        if labels:
            binder = Binder(labels, func)
        else:
            binder = Binder(func)
        fill = False if size else True
        binder.builder = RadioBuilder(group=group, style=style, align=align, fill_bottom=fill, caption=caption, caption_style=caption_style)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def popup(size='pack', order=None, style=None):
    """
    Decorator that produces a PopUp View

    The decorated function is expected to return a instance of PopUpView.

    To Display the pop it is required to call popup.show() on the decorated function.
    To register an action listener to be notified when the PopUp is closed it is required to use the uibind.listener
    decorator.

    Example::

        @uibind.popup()
        def sample_popup(self):
            return SamplePopup()

        @sample_popup.uibind.listener
        def on_popup_close(self, obj, value):  # A PopUp View can return a value by calling self.set_value(<value>)
            pass

        def popup_caller(self):
            self.sample_popup.popup.show()

    :param size: one of:
            'pack' - minimum size
            number - a integer of the required size
            tuple - as expected by the container. Eg: ('weight', 1)
    :param order: order of the element on the view from top to bottom
    :param style: color style to be applied to the element. Expected to be a tuple with 2 elements being pallet entry
        names like ('style_name', 'focus_style_name')
    :return: decorator function
    """
    def bind(func):
        binder = Binder(func)
        binder.builder = PopupBuilder(style=style)
        binder.size = size
        binder.order = order
        func.uibind = binder
        return func
    return bind


def propagate_exception(func):
    func.is_skip_error_wrapper = 1
    return func


class Binder(object):

    def __init__(self, source_func=None, value_func=None, element_bind=None, size='pack'):
        self.source = source_func
        self.value = value_func
        self.builder = None
        self.order = None
        self.size = size
        self.element_bind = element_bind

    def listener(self, value_func):
        self.value = value_func
        return value_func

    def build(self, ui_instance):
        return self.builder.build(ui_instance, self)

    def get_element_binding(self, default=None, can_bind_to_value=True):
        if self.element_bind:
            return self.element_bind
        elif callable(self.source):
            return self.source
        elif can_bind_to_value and callable(self.value):
            return self.value
        else:
            return default


class BackingUi(object):
    def __init__(self):
        self._connected_signals = []
        self._value_map = {}

    def add_connected_signal(self, connect_args):
        if connect_args:
            self._connected_signals.append(connect_args)

    def register_value_map(self, source_func, value_widget):
        if source_func:
            self._value_map[self._as_key(source_func)] = value_widget

    def get_value(self, element_key):
        element = self.get_element(element_key)
        return element.get_value() if element else None

    def get_element(self, element_key):
        return self._value_map.get(self._as_key(element_key))

    @staticmethod
    def _as_key(key):
        return key.__name__ if callable(key) and key.__name__ else key


def setup_ui_instance(instance):
    if not hasattr(instance, "__ui"):
        instance.__ui = BackingUi()


def backing_ui(instance):
    if not hasattr(instance, "__ui"):
        return None
    return instance.__ui


class WidgetBuilder(object):
    """Base Builder class. defines the expected interface for all widget builders"""

    def __init__(self, binder=None):
        self._default_binder = binder

    def build(self, instance, binder):
        binder = self._merge_default_binder(binder)
        return self.do_build(instance, binder or self._default_binder)

    def do_build(self, instance, binder):
        pass

    def add_connected_signal(self, instance, connect_args):
        self.setup(instance)
        backing_ui(instance).add_connected_signal(connect_args)

    def register_value_map(self, instance, source_func, value_widget):
        self.setup(instance)
        backing_ui(instance).register_value_map(source_func, value_widget)

    @staticmethod
    def apply_style(widget, style):
        if style:
            return u.AttrMap(widget, *style)
        else:
            return widget

    @staticmethod
    def setup(instance):
        setup_ui_instance(instance)

    def _merge_default_binder(self, binder):
        if binder and self._default_binder:
            binder.source = binder.source if binder.source else self._default_binder.source
            binder.value = binder.value if binder.value else self._default_binder.value
            binder.element_bind = binder.element_bind if binder.element_bind else self._default_binder.element_bind
            binder.builder = binder.builder if binder.builder else self._default_binder.builder
            binder.order = binder.order if binder.order else self._default_binder.order
            binder.size = binder.size if binder.size else self._default_binder.size
        else:
            return binder


class TextInputBuilder(WidgetBuilder):

    def __init__(self, caption=None, style=None, action_on_enter=True, fill_bottom=False, disable_on_none=False, **kwargs):
        super(TextInputBuilder, self).__init__(**kwargs)
        self._disable_on_none = disable_on_none
        self._fill_bottom = fill_bottom
        self._action_on_enter = action_on_enter
        self._caption = caption
        self._style = style

    def do_build(self, instance, binder):
        if self._action_on_enter:
            edit = ActionEdit(self._caption or '')
        else:
            edit = u.Edit(self._caption or '')

        if binder.source:
            if callable(binder.source):
                val = binder.source(instance)
            else:
                val = binder.source

            if val:
                edit.set_edit_text(val)
            elif val is None and self._disable_on_none:
                return None

        if binder.value:
            connect_args = (edit, "change", binder.value, None, None, [instance])
            u.connect_signal(*connect_args)
            self.add_connected_signal(instance, connect_args)

        edit.get_value = lambda: edit.get_edit_text()
        self.register_value_map(instance, binder.get_element_binding(binder.source), edit)

        return u.Filler(self.apply_style(edit, self._style), valign='top') if self._fill_bottom else self.apply_style(edit, self._style)


class ActionEdit(u.Edit):

    def keypress(self, size, key):
        if key == 'enter':
            self._emit('change', 'enter')
            return None
        return super(ActionEdit, self).keypress(size, key)


class ButtonBuilder(WidgetBuilder):

    def __init__(self, style, align='right', fill_bottom=False):
        super(ButtonBuilder, self).__init__()
        self._fill_bottom = fill_bottom
        self._align = align
        self._style = style

    def do_build(self, instance, binder):
        labels = []
        if callable(binder.source):
            val = binder.source(instance)
            labels = _to_string_list(val)
        else:
            labels = _to_string_list(binder.source)

        if labels is None:
            return None

        buttons = []
        bar_contents = []
        bar_total_size = 0
        for label in labels:
            button = u.Button(label)
            self._register_shortcut(instance, label, button)
            connect_args = (button, "click", binder.value, self._remove_shortcut_mark(label), None, [instance])
            u.connect_signal(*connect_args)
            self.add_connected_signal(instance, connect_args)

            button.get_value = lambda: label
            buttons.append(button)
            button_size = len(label) + 4
            bar_contents.append((button_size, self.apply_style(button, self._style)))
            bar_total_size += button_size

        bar_total_size += len(buttons) - 1

        if len(buttons) > 0:
            self.register_value_map(instance, binder.get_element_binding(binder.value), buttons if len(buttons) > 1 else buttons[0])

        bar = u.Columns(bar_contents, 1)

        aligned_bar = u.Padding(bar, align=self._align, width=bar_total_size)

        return u.Filler(aligned_bar, valign='top') if self._fill_bottom else aligned_bar

    @staticmethod
    def _register_shortcut(instance, label, button):
        m = re.search(r'\[([a-zA-Z0-9])\]', label)
        if m:
            instance.register_shortcut(m.group(1).lower(), 'keypress', button, (None, 'enter'))

    @staticmethod
    def _remove_shortcut_mark(label):
        return re.sub(r'\[([a-zA-Z0-9])\]', r'\1', label)


class RadioBuilder(WidgetBuilder):

    def __init__(self, style, align='left', fill_bottom=False, group=None, caption=None, caption_style=None):
        super(RadioBuilder, self).__init__()
        self._caption_style = caption_style
        self._caption = caption
        self._fill_bottom = fill_bottom
        self._align = align
        self._style = style
        self._group = group

    def do_build(self, instance, binder):
        labels = []
        if callable(binder.source):
            val = binder.source(instance)
            labels = _to_string_list(val)
        else:
            labels = _to_string_list(binder.source)

        if labels is None:
            return None

        if len(labels) > 0 and not isinstance(labels[0], (list, tuple)):
            labels = [labels]

        buttons = []
        bar_contents = []
        for grp in labels:
            group = self._group or []
            grp_contents = []
            grp_buttons = []
            for label in grp:
                radio = u.RadioButton(group, label)

                buttons.append(radio)
                grp_buttons.append(radio)
                button_size = len(label) + 4
                grp_contents.append((button_size, self.apply_style(radio, self._style)))

                if binder.value:
                    connect_args = (radio, "change", binder.value, label, None, [instance])
                    u.connect_signal(*connect_args)
                    self.add_connected_signal(instance, connect_args)

            bar_line = u.Columns(grp_contents, 3)
            bar_line.buttons = grp_buttons
            bar_line.get_value = lambda s: [r for r in s.buttons if r.state][0].label
            bar_contents.append(bar_line)

        if self._caption:
            bar = u.Columns((('pack', self.apply_style(u.Text(self._caption), self._caption_style)), u.Pile(bar_contents)), dividechars=1)
        else:
            bar = u.Pile(bar_contents)
        bar.get_value = lambda: [line.get_value(line) for line in bar_contents]
        bar.get_options = lambda: buttons
        if len(buttons) > 0:
            self.register_value_map(instance, binder.get_element_binding(binder.value), bar)

        aligned_bar = u.Padding(bar, align=self._align, width='pack')

        return u.Filler(aligned_bar, valign='top') if self._fill_bottom else aligned_bar


class TextBuilder(WidgetBuilder):

    def __init__(self, align='left', wrap='space', style=None, binder=None, fill_bottom=False, valign='top'):
        super(TextBuilder, self).__init__(binder)
        self._valign = valign
        self._fill_bottom = fill_bottom
        self._style = style
        self._wrap = wrap
        self._align = align

    def do_build(self, instance, binder):
        if callable(binder.source):
            val = binder.source(instance)
        else:
            val = binder.source

        if val is None:
            return None

        text = u.Text(str(val), self._align, self._wrap)
        text.get_value = lambda: text.get_text()

        self.register_value_map(instance, binder.get_element_binding(binder.source), text)
        styled_text = self.apply_style(text, self._style)
        return u.Filler(styled_text, valign=self._valign) if self._fill_bottom else styled_text


class ProgressBarBuilder(WidgetBuilder):

    def __init__(self, align='left', valign='top', style_normal=None, style_complete=None, style_satt=None, binder=None, done_at=100, fill_bottom=False, width=u.RELATIVE_100):
        super(ProgressBarBuilder, self).__init__(binder)
        self._width = width
        self._done_at = done_at
        self._style_satt = style_satt
        self._style_complete = style_complete
        self._style_normal = style_normal
        self._fill_bottom = fill_bottom
        self._align = align
        self._valign = valign

    def do_build(self, instance, binder):
        if callable(binder.source):
            val = binder.source(instance)
        else:
            val = binder.source

        if val is None:
            return None

        current_value = 0
        if isinstance(val, (list, tuple)):
            self._done_at = int(val[0])
            current_value = int(val[1])

        bar = u.ProgressBar(self._style_normal, self._style_complete, current_value, self._done_at, self._style_satt)
        bar.get_value = lambda: bar.current
        self.register_value_map(instance, binder.get_element_binding(binder.source), bar)

        padded_bar = u.Padding(bar, align=self._align, width=self._width)

        return u.Filler(padded_bar, valign=self._valign) if self._fill_bottom else padded_bar


class TextTableBuilder(WidgetBuilder):
    """Builds a table out of a list of list"""

    def __init__(self, align='left', style=None, binder=None, col_sizes=None, buffer_size=100):
        super(TextTableBuilder, self).__init__(binder)
        self._buffer_size = buffer_size
        self._style = style
        self._align = align
        self._col_sizes = col_sizes

    def do_build(self, instance, binder):
        if callable(binder.source):
            data = binder.source(instance)
        else:
            data = binder.source

        if data is None:
            return None

        if not isinstance(data, NavigableDataSource):
            data = NavigableDataSource(_to_string_list(data))

        list_walker = BufferedListWalker(self._buffer_size, data, _RowItemBuilder(self._align, self._style, self._col_sizes), instance)
        table = u.ListBox(list_walker)

        table.get_value = lambda: table.focus.get_value(table.focus) if table.focus else None
        table.refresh = lambda: list_walker.flush() or list_walker.set_focus(table.get_focus()[1] or 0) if table.get_focus()[0] else None

        self.register_value_map(instance, binder.get_element_binding(binder.source), table)
        return table


class _RowItemBuilder(WidgetBuilder):

    def __init__(self, align='left', style=None, col_sizes=None, **kwargs):
        super(_RowItemBuilder, self).__init__(**kwargs)
        self._col_sizes = col_sizes
        self._style = style
        self._align = align

    def do_build(self, instance, binder):
        data_line = binder.source
        row_items = []
        for col in xrange(len(data_line)):
            item = u.Text(str(data_line[col]), align=self._col_align(col))
            item = self.apply_style(item, self._col_style(col))
            col_size = self._col_size(col)
            row_items.append((col_size, item) if col_size else item)
        columns = u.Columns(row_items, dividechars=1)
        columns._value = data_line
        columns.get_value = lambda me: me._value

        return columns

    def _col_align(self, col):
        return self._get_string_or_list_item(col, self._align)

    def _col_style(self, col):
        return self._get_string_or_list_item(col, self._style)

    def _col_size(self, col):
        return self._get_string_or_list_item(col, self._col_sizes)

    @staticmethod
    def _get_string_or_list_item(col, data):
        if data is None:
            return None
        elif isinstance(data, basestring):
            return data
        elif isinstance(data, (list, tuple)):
            if isinstance(data[0], (list, tuple)):
                if len(data) > col:
                    return data[col]
                else:
                    return None
            else:
                return data
        else:
            return None


class DividerBuilder(WidgetBuilder):

    def __init__(self, char=u'', top=0, bottom=0, style=None, binder=None):
        super(DividerBuilder, self).__init__(binder)
        self._style = style
        self._bottom = bottom
        self._top = top
        self._char = char

    def do_build(self, instance, binder):
        if callable(binder.source):
            val = binder.source(instance)
        else:
            val = binder.source

        val = val or self._char

        if val is None:
            return None

        div = u.Divider(val, self._top, self._bottom)
        div.get_value = lambda: ''

        self.register_value_map(instance, binder.get_element_binding(binder.source), div)
        return self.apply_style(div, self._style)


class PopUp(View, WidgetBuilder):

    def __init__(self, view, binder, style, **kwargs):
        super(PopUp, self).__init__(**kwargs)
        self._style = style
        self._binder = binder
        self._view_instance = view
        self._connect_signal_args = None
        self._popup_view = None

    def do_build(self, instance, binder):
        if callable(binder.source):
            view = binder.source(instance)
        else:
            view = binder.source

        if view is None:
            return None

        if isinstance(view, View):
            self._popup_view = view
            view.set_display(instance.get_display())
            view._before_build()
            widget = view.build_ui()
            self._connect_signal_args = (view, 'close_popup', self.on_popup_close)
            u.connect_signal(*self._connect_signal_args)
        elif not isinstance(u.Widget):
            raise ValueError('Expected a View or Widget.')
        else:
            widget = view
            view.get_value = lambda: None

        self.register_value_map(instance, binder.get_element_binding(binder.source), view)
        return self.apply_style(widget, self._style)

    def build_ui(self):
        widget = self.do_build(self._view_instance, self._binder)
        if widget is None:
            return None

        if self._popup_view:
            popup = widget
        else:
            popup = u.Overlay(u.Padding(widget, align='center', left=2, right=2), u.SolidFill(u'\N{LIGHT SHADE}'),
                              align='center', width=('relative', 60),
                              valign='middle', height=('relative', 60),
                              min_width=20, min_height=9)
        return popup

    def on_popup_close(self, view, value):
        self.close()
        if callable(self._binder.value):
            self._binder.value(self._view_instance, view, value)

    def close(self):
        self._view_instance.get_display().back()
        if self._connect_signal_args:
            u.disconnect_signal(*self._connect_signal_args)

    def show(self):
        self._view_instance.get_display().show_view(self)

    def after_build(self):
        if self._popup_view:
            self._popup_view.after_build()

    def after_show(self):
        if self._popup_view:
            self._popup_view.after_show()

    def get_element_of(self, key_view_element):
        if self._popup_view:
            return self._popup_view.get_element_of(key_view_element)
        return None

    def handle_input(self, key):
        if self._popup_view:
            self._popup_view.handle_input(key)

    def get_display(self):
        if self._popup_view:
            return self._popup_view.get_display()
        return None

    def get_ui_element(self):
        if self._popup_view:
            return self._popup_view.get_ui_element()
        return None

    def set_display(self, display):
        if self._popup_view:
            self._popup_view.set_display(display)

    def get_value_of(self, key_view_element):
        if self._popup_view:
            return self._popup_view.get_value_of(key_view_element)
        return None


class PopupBuilder(WidgetBuilder):

    def __init__(self, style=None, **kwargs):
        super(PopupBuilder, self).__init__(**kwargs)
        self._style = style

    def do_build(self, instance, binder):
        pop_up = PopUp(instance, binder, self._style)

        if callable(binder.source):
            binder.source.popup = pop_up

        return None


class ListBuilder(WidgetBuilder):

    def __init__(self, item_builder, buffer_size=50, style=None, **kwargs):
        super(ListBuilder, self).__init__(**kwargs)
        self._style = style
        self._item_builder = item_builder
        self._buffer_size = buffer_size

    def do_build(self, instance, binder):
        if callable(binder.source):
            data = binder.source(instance)
        else:
            data = binder.source

        if data is None:
            return None

        if not isinstance(data, NavigableDataSource):
            data = NavigableDataSource(_to_string_list(data))

        list_walker = BufferedListWalker(self._buffer_size, data, self._item_builder, instance)
        list_box = u.ListBox(list_walker)
        list_box.get_value = lambda: list_box.focus.get_value() if list_box.focus else None

        def refresh():
            list_walker.flush()
            # logger.debug('list_box focus: %s', str(list_box.get_focus()))
            # logger.debug('list_walker focus: %s', str(list_walker.get_focus()))
            curr_item, curr_idx = list_box.get_focus()
            if curr_item:
                list_walker.set_focus(curr_idx)
            else:
                list_walker.set_focus(0)
                if list_walker.get_focus()[0]:
                    list_box.set_focus(0)
                else:
                    list_box._invalidate()

        list_box.refresh = refresh

        self.register_value_map(instance, binder.get_element_binding(binder.source), list_box)
        return self.apply_style(u.LineBox(list_box), self._style)


class NavigableDataSource(object):
    def __init__(self, sequence):
        self._sequence = sequence

    def fetch(self, start, size):
        end = min(start + size, len(self._sequence))
        return self._sequence[start:end]


class BufferedListWalker(u.ListWalker, list):

    def __init__(self, buffer_size, nav_data_source, item_builder, ui_instance):
        u.ListWalker.__init__(self)
        self._ui_instance = ui_instance
        self._item_builder = item_builder
        self._buffer_size = buffer_size
        self._buffer_center_offset = int((buffer_size - 1) / 2)
        self._offset_start = 0
        self._ds = nav_data_source
        self.focus = 0
        self._first_known_empty_index = sys.maxint
        self._exception_handler = ui_instance.get_display().exception_handler

    def get_focus(self):
        try:
            return self._get_value_at(self.focus)
        except Exception as e:
            self._handle_exception(e)
            return None, None

    def set_focus(self, focus):
        self.focus = focus
        self._modified()

    def get_next(self, start_from):
        try:
            return self._get_value_at(start_from + 1)
        except Exception as e:
            self._handle_exception(e)
            return None, None

    def get_prev(self, start_from):
        try:
            return self._get_value_at(start_from - 1)
        except Exception as e:
            self._handle_exception(e)
            return None, None

    def flush(self):
        del self[:]
        self._first_known_empty_index = sys.maxint

    def _modified(self):
        u.ListWalker._modified(self)

    def _get_value_at(self, pos):
        if self._offset_start <= pos < self._offset_start + len(self):
            # logger.debug('ListWalker: position=%d is in the buffer', pos)
            return self[pos - self._offset_start], pos

        if pos < 0 or pos >= self._first_known_empty_index:
            # logger.debug('Empty index: %d', pos)
            return None, None

        new_offset = pos - self._buffer_center_offset
        if new_offset < 0:
            new_offset = 0
        # logger.debug('ListWalker: current_offset=%d, new_offset=%d, position=%d', self._offset_start, new_offset, pos)
        if new_offset < self._offset_start:
            # going back
            items_to_load = min(new_offset + self._buffer_size, self._offset_start)
            new_items = self._ds.fetch(new_offset, items_to_load)
            if new_items and len(new_items) > 0:
                items_loaded = len(new_items)
                if items_loaded == self._buffer_size:
                    self._replace_all_items(new_items)
                else:
                    del self[items_loaded * -1:]
                    at = 0
                    for item in new_items:
                        self.insert(at, self._build_item(item))
                        at += 1
        else:
            # going forward
            if new_offset > self._offset_start + len(self):
                new_items = self._ds.fetch(new_offset, self._buffer_size)
                self._replace_all_items(new_items)
            else:
                fetch_start = self._offset_start + len(self)
                items_to_load = new_offset + self._buffer_size - fetch_start
                new_items = self._ds.fetch(fetch_start, items_to_load)
                if new_items and len(new_items) > 0:
                    for item in new_items:
                        self.append(self._build_item(item))

                if new_offset > self._offset_start:
                    del self[0:min(new_offset - self._offset_start, len(self))]

        self._offset_start = new_offset

        if self._offset_start <= pos < self._offset_start + len(self):
            buffer_position = pos - self._offset_start
            return self[buffer_position], pos
        else:
            self._first_known_empty_index = min(self._first_known_empty_index, pos)
            return None, None

    def _replace_all_items(self, new_items):
        del self[:]
        for item in new_items:
            self.append(self._build_item(item))

    def _build_item(self, item):
        return self._item_builder.build(self._ui_instance, Binder(item))

    def set_modified_callback(self, callback):
        pass

    def _handle_exception(self, e):
        if self._exception_handler:
            self._exception_handler(e, self._ui_instance)
        else:
            raise e


class FileBrowserBuilder(WidgetBuilder):

    def __init__(self, style=None, item_style=None, item_order_by=None, show_files=True, **kwargs):
        super(FileBrowserBuilder, self).__init__(**kwargs)
        self._show_files = show_files
        self._item_order_by = item_order_by
        self._item_style = item_style
        self._style = style

    def do_build(self, instance, binder):
        if callable(binder.source):
            data = binder.source(instance)
        else:
            data = binder.source

        if data is None:
            return None

        file_browser = FileBrowser(data, style=self._item_style, order_by=self._item_order_by, show_files=self._show_files)

        self.register_value_map(instance, binder.get_element_binding(binder.source), file_browser)
        return self.apply_style(u.LineBox(file_browser), self._style)


class FileBrowser(u.TreeListBox):

    def __init__(self, start_path, order_by=None, style=None, filter_pattern=None, show_files=True):
        self._show_files = show_files
        self._style = style
        self._start_path = start_path
        self._last_size = None
        self._order_by = order_by
        self._filter_pattern = filter_pattern

        if not os.path.exists(start_path):
            raise ValueError('Invalid path: ' + str(start_path))

        if os.path.isfile(start_path):
            start_path = os.path.dirname(start_path)

        self._walker = u.TreeWalker(DirectoryNode(start_path, order_by=order_by, style=style, filter_pattern=filter_pattern, show_files=self._show_files))
        super(FileBrowser, self).__init__(self._walker)

    def get_value(self):
        value = None
        node_w = self.focus
        if node_w:
            value = node_w.get_node().get_value()

        return value

    def render(self, size, focus=False):
        self._last_size = size
        return super(FileBrowser, self).render(size, focus)

    def set_start_path(self, path):
        self._start_path = path
        self._walker.set_focus(DirectoryNode(self._start_path, order_by=self._order_by, filter_pattern=self._filter_pattern, show_files=self._show_files, style=self._style))

    def order_by(self, order_func):
        current_path = self.get_value()
        self._order_by = order_func
        self._walker.set_focus(DirectoryNode(self._start_path, order_by=order_func, filter_pattern=self._filter_pattern, show_files=self._show_files, expanded_path=current_path, style=self._style))

    def filter_by(self, filter_pattern):
        current_path = self.get_value()
        self._filter_pattern = filter_pattern
        self._walker.set_focus(DirectoryNode(self._start_path, order_by=self._order_by, filter_pattern=self._filter_pattern, show_files=self._show_files, expanded_path=current_path, style=self._style))


class FileTreeWidget(u.TreeWidget):

    def __init__(self, node, style=None):
        self._style = style
        super(FileTreeWidget, self).__init__(node)

    def selectable(self):
        return True

    def load_inner_widget(self):
        text = u.Text(self.get_display_text())
        modified = u.Text(time.strftime('%b %d %H:%M:%S ', time.localtime(os.path.getmtime(self.get_node().get_value()))))

        file_w = u.Columns((text, ('pack', modified)))
        return u.AttrMap(file_w, *self._style) if self._style else file_w

    def get_display_text(self):
        return self.get_node().get_key()


class EmptyWidget(u.TreeWidget):

    def get_display_text(self):
        return '(empty directory)'


class ErrorWidget(u.TreeWidget):

    def get_display_text(self):
        return 'error', "(error/permission denied)"


class DirectoryWidget(u.TreeWidget):

    def __init__(self, node, expanded=False, style=None):
        self._style = style
        super(DirectoryWidget, self).__init__(node)
        self.expanded = expanded
        self.update_expanded_icon()

    def selectable(self):
        return True

    def load_inner_widget(self):
        text = u.Text(self.get_display_text())
        return u.AttrMap(text, *self._style) if self._style else text

    def get_display_text(self):
        node = self.get_node()
        if node.get_depth() == 0:
            return node.get_value()
        else:
            return node.get_key()


class FileNode(u.TreeNode):

    def __init__(self, path, parent=None, style=None):
        self._style = style
        key = os.path.basename(path)
        super(FileNode, self).__init__(path, key=key, parent=parent)

    def load_widget(self):
        return FileTreeWidget(self, style=self._style)


class EmptyNode(u.TreeNode):

    def load_widget(self):
        return EmptyWidget(self)


class ErrorNode(u.TreeNode):

    def load_widget(self):
        return ErrorWidget(self)


class DirectoryNode(u.ParentNode):

    def __init__(self, path, parent=None, order_by=None, expanded_path=None, style=None, filter_pattern=None, show_files=True):
        self._show_files = show_files
        self._filter_pattern = filter_pattern
        self._style = style
        self._expanded_path = expanded_path
        self._order_by = order_by
        self.dir_count = 0
        if path == _dir_sep:
            key = None
        else:
            key = os.path.basename(path)
        super(DirectoryNode, self).__init__(path, key=key, parent=parent)

    def load_child_keys(self):
        dirs = []
        files = []
        try:
            path = self.get_value()
            paths = [{'name': item, 'path': os.path.join(path, item)} for item in os.listdir(path)]

            if self._filter_pattern:
                matched = []
                patterns = self._filter_pattern.split(';')
                for item in paths:
                    for pattern in patterns:
                        if fnmatch.fnmatch(item['name'], pattern):
                            matched.append(item)
                            break
                paths = matched

            if self._order_by:
                paths.sort(key=self._order_by)

            # separate dirs and files
            for item in paths:
                if os.path.isdir(item['path']):
                    dirs.append(item['name'])
                elif self._show_files:
                    files.append(item['name'])
        except OSError:
            depth = self.get_depth() + 1
            self._children[None] = ErrorNode(self, parent=self, key=None, depth=depth)
            return [None]

        self.dir_count = len(dirs)

        keys = dirs + files
        if len(keys) == 0:
            depth = self.get_depth() + 1
            self._children[None] = EmptyNode(self, parent=self, key=None, depth=depth)
            keys = [None]
        return keys

    def load_child_node(self, key):

        index = self.get_child_index(key)
        if key is None:
            return EmptyNode(None)
        else:
            path = os.path.join(self.get_value(), key)
            if index < self.dir_count:
                return DirectoryNode(path, parent=self, order_by=self._order_by, expanded_path=self._expanded_path, style=self._style, show_files=self._show_files)
            else:
                path = os.path.join(self.get_value(), key)
                return FileNode(path, parent=self, style=self._style)

    def load_widget(self):
        return DirectoryWidget(self, expanded=self.is_expanded(), style=self._style)

    def is_expanded(self):
        if self.get_depth() == 0:
            return True
        if self._expanded_path and self.get_value() in self._expanded_path:
            return True

        return False


def _to_string_list(value):
    if isinstance(value, basestring):
        return [value]
    elif isinstance(value, (list, tuple)):
        return value
    elif value is None:
        return None
    else:
        return [str(value)]


def _get_dir_sep():
    return getattr(os.path, 'sep', '/')

_dir_sep = _get_dir_sep()

_convert_int = lambda value_text: int(value_text) if value_text.isdigit() else value_text
_alphanum_key = lambda key: [_convert_int(c) for c in re.split('([0-9]+)', key)]

file_sort_by_name_asc = lambda item: _alphanum_key(item['name'].lower())
file_sort_by_last_modified_desc = lambda item: os.path.getmtime(item['path']) * -1
