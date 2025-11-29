from config.settings import SETTINGS
from glueous.Reader import Reader

if __name__ == '__main__':
    # import multiprocessing
    # multiprocessing.freeze_support()  # Windows 必需

    reader = Reader(SETTINGS)
    reader.mainloop()
