from config.settings import SETTINGS
from glueous.Reader import Reader

if __name__ == '__main__':
    reader = Reader(SETTINGS)
    reader.mainloop()
