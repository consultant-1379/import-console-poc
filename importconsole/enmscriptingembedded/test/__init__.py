import time
time_sleep = time.sleep


def disable_sleep():
    time.sleep = lambda seconds: None


def restore_sleep():
    time.sleep = time_sleep

disable_sleep()
