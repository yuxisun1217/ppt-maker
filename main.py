"""Conference host script PPT generator — entry point."""
import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    from database.db import init_db
    init_db()

    from ui.login_window import LoginWindow

    def on_login(user):
        from ui.main_window import MainWindow
        app = MainWindow(user)
        app.run()

    login = LoginWindow(on_login)
    login.run()


if __name__ == '__main__':
    main()
