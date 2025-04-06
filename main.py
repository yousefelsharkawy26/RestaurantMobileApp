from kivymd.uix.pickers.datepicker.datepicker import date
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.recycleview import RecycleView
from kivy.uix.button import Button  # الاستيراد المطلوب
from kivy.clock import Clock
from kivy.properties import NumericProperty, StringProperty, BooleanProperty
from kivy.graphics import RoundedRectangle, Color  # للتصميم
from kivy.lang import Builder
import sqlite3
import websockets
import json
import asyncio
import threading
import arabic_reshaper
import bidi.algorithm
import datetime
from kivy.uix.popup import Popup
from kivymd.uix.pickers import MDDatePicker
from kivymd.uix.menu import MDDropdownMenu
from kivymd.app import MDApp 

# إنشاء قاعدة البيانات
conn = sqlite3.connect('orders.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS orders 
            (id INTEGER PRIMARY KEY, 
            orderNumber INTEGER,
            customerName TEXT,
            totalAmount REAL,
            orderDate TEXT,
            isPaid INTEGER,
            userName TEXT)''')
conn.commit()

class WebSocketClient(threading.Thread):
    def __init__(self, app):
        super().__init__(daemon=True)
        self.app = app
        self.websocket_url = "ws://localhost:8765/orders"
        self.is_connected = False

    async def connect(self):
        try:
            async with websockets.connect(self.websocket_url) as websocket:
                self.is_connected = True
                if self.is_connected:
                    conn = sqlite3.connect('orders.db', check_same_thread=False)
                    c = conn.cursor()
                    c.execute("DELETE FROM orders")
                    conn.commit()
                    conn.close()

                Clock.schedule_once(lambda dt: self.app.update_server_status(True))
                while True:
                    message = await websocket.recv()
                    self.handle_message(message)
                
        except Exception as e:
            self.is_connected = False
            Clock.schedule_once(lambda dt: self.app.update_server_status(False))
            print("Connection error:", e)

    def handle_message(self, message):
        try:
            data = json.loads(message)
            required_fields = [
                'id',
                'orderNumber',
                'customerName',
                'totalAmount',
                'orderDate',
                'isPaid',
                'userName'
            ]
            
            if all(field in data for field in required_fields):
                conn = sqlite3.connect('orders.db', check_same_thread=False)
                c = conn.cursor()
                c.execute('''INSERT INTO orders VALUES 
                            (?, ?, ?, ?, ?, ?, ?)''',
                        (
                            data['id'],
                            data['orderNumber'],
                            data['customerName'],
                            data['totalAmount'],
                            data['orderDate'],
                            int(data['isPaid']),
                            data['userName']
                        ))
                conn.commit()
                conn.close()
                Clock.schedule_once(lambda dt: self.app.update_display())
        except Exception as e:
            print("Error handling message:", e)

    def run(self):
        asyncio.new_event_loop().run_until_complete(self.connect())

class CustomButton(Button):  # التصحيح هنا
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind()
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)

class OrderRow(BoxLayout):
    orderNumber = NumericProperty(0)
    customerName = StringProperty('')
    totalAmount = NumericProperty(0.0)
    orderDate = StringProperty('')
    isPaid = BooleanProperty(False)
    userName = StringProperty('')

class RV(RecycleView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.refresh_data()
    
    def refresh_data(self, filter_type='all'):
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()

        if filter_type == 'all':
            c.execute("SELECT * FROM orders")
        elif filter_type == 'today':
            today = datetime.date.today().strftime('%Y-%m-%d')
            c.execute("SELECT * FROM orders WHERE date(orderDate) = ?", (today,))
        elif filter_type == 'date':
            date = App.get_running_app().show_date_picker()
            # يمكنك إضافة منطق اختيار تاريخ محدد هنا
            print('date = ', date)

        data = [{
            'id': row[0],
            'orderNumber': row[1],
            'customerName': row[2],
            'totalAmount': row[3],
            'orderDate': row[4],
            'isPaid': bool(row[5]),
            'userName': row[6]
        } for row in c.fetchall()]
        
        c.execute("SELECT SUM(totalAmount) FROM orders")
        total = c.fetchone()[0] or 0.0
        conn.close()
        self.data = data
        return total

class MainLayout(BoxLayout):
    def update_total(self, total):
        try:
            if hasattr(self, 'ids') and 'total_salary_label' in self.ids:
                self.ids.total_salary_label.text = f"${total:.2f}"
        except Exception as e:
            print("Error updating total:", e)


class KivyApp(MDApp):
    def build(self):
        self.ws_client = WebSocketClient(self)
        self.ws_client.start()
        self.theme_cls.theme_style = "Dark"
        return MainLayout()


    def show_date_picker(self):
        date_dialog = MDDatePicker()
        date_dialog.bind(on_save=self.on_date_selected)
        date_dialog.open()
        return date(day=date_dialog.sel_day, month=date_dialog.sel_month, year=date_dialog.sel_year)

    def set_filter(self, text):
        self.root.ids.filter_item.text = self.arabic_converter(text)
        self.menu.dismiss()

    def on_date_selected(self, instance, date, date_range):
        conn = sqlite3.connect('orders.db', check_same_thread=False)
        c = conn.cursor()
        date = today = date.strftime('%Y-%m-%d')
        c.execute("SELECT * FROM orders WHERE date(orderDate) = ?", (date,))
        data = [{
            'id': row[0],
            'orderNumber': row[1],
            'customerName': row[2],
            'totalAmount': row[3],
            'orderDate': row[4],
            'isPaid': bool(row[5]),
            'userName': row[6]
        } for row in c.fetchall()]
        rv = self.root.ids.rv
        rv.data = data

        print("Date selected:", date)

    def arabic_converter(self, text):  # التصحيح هنا
        try:
            reshaped = arabic_reshaper.reshape(text)
            return bidi.algorithm.get_display(reshaped)
        except Exception as e:
            print(f"Error converting text: {e}")
            return text

    def update_display(self, *args):
        try:
            if self.root and hasattr(self.root, 'ids'):
                if 'rv' in self.root.ids:
                    rv = self.root.ids.rv
                    total = rv.refresh_data()
                    self.root.update_total(total)
        except Exception as e:
            print("Error in update_display:", e)

    def update_server_status(self, is_connected):
        status_label = self.root.ids.server_status
        status_label.font = 'arial.ttf'
        if is_connected:
            status_label.text = self.arabic_converter("متصل")
            status_label.color = (0, 1, 0, 1)
        else:
            status_label.text = self.arabic_converter("غير متصل")
            status_label.color = (1, 0, 0, 1)

    def check_server_status(self):
        # if not self.ws_client.is_connected:
        self.ws_client = WebSocketClient(self)
        self.ws_client.start()
    
    def filter_orders(self, text_filter):
        rv = self.root.ids.rv
        rv.refresh_data(text_filter)


if __name__ == '__main__':
    KivyApp().run()