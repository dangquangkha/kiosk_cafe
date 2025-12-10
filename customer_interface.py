from tkinter import messagebox
import requests
import qrcode
import time
from PIL import Image, ImageTk
import io
import os
import speech_recognition as sr
from openai import OpenAI
import threading
import pygame
import re
from dotenv import load_dotenv
import customtkinter as ctk

# --- CẤU HÌNH CỦA BẠN ---
HEROKU_APP_URL = "https://khai-flask-todo-app-a81bf71c8cf2.herokuapp.com/"
# -------------------------

# --- CẤU HÌNH VOICE (Giữ nguyên) ---
try:
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        raise ValueError("OPENAI_API_KEY không được tìm thấy.")
    client = OpenAI(api_key=openai_api_key)
except Exception as e:
    # MODIFIED: Không hiển thị popup ở đây vì root chưa được tạo
    print(f"Lỗi OpenAI Key: Không tìm thấy OPENAI_API_KEY. {e}")
    # exit() # Cân nhắc thoát nếu không có key

recognizer = sr.Recognizer()
pygame.mixer.init()
# -------------------------

# --- BIẾN TOÀN CỤC ---
current_orderId = None
root = None
menu_items = {}
shopping_cart = {}
status_label = None
menu_frame = None
checkout_frame = None
payment_frame = None
cart_badge_label = None
checkout_total_label = None
checkout_details_label = None
qr_label = None
voice_button = None
cart_drawer = None
cart_drawer_items_frame = None
cart_drawer_total_label = None
toast_label = None
latest_cart_total = 0
conversation_history = []
chat_system_prompt = ""
idle_frame = None
is_busy = False  # Biến kiểm tra xem robot đang rảnh hay đang phục vụ
# --- BIẾN MỚI CHO LOGIC ROBOT ---
CURRENT_TABLE = None # Sẽ lưu số bàn robot đang phục vụ
CURRENT_SERVICE_REQUEST_ID = None # Sẽ lưu ID của yêu cầu phục vụ
# ---------------------------------

# --- THEME CONSTANTS ---
APP_BG_COLOR = "#F5F7FB"
CARD_BG_COLOR = "#FFFFFF"
HIGHLIGHT_COLOR = "#E2E8F0"
TEXT_PRIMARY = "#0F172A"
TEXT_SECONDARY = "#475467"
ACCENT_COLOR = "#2563EB"
SUCCESS_COLOR = "#16A34A"
WARNING_COLOR = "#F97316"
DANGER_COLOR = "#DC2626"
FONT_FAMILY = "Inter"

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("green")

# --- HÀM TẢI MENU (Giữ nguyên) ---
def load_menu_from_server():
    # ... (Giữ nguyên toàn bộ nội dung hàm) ...
    global menu_items
    try:
        url = f"{HEROKU_APP_URL}/api/get-menu"
        print(f"Đang tải menu từ {url}...")
        
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            menu_items = response.json()
            print(f"Tải menu thành công: {menu_items}")
            
            if not menu_items:
                 # MODIFIED: Không hiển thị popup
                 print("Lỗi Menu: Không tìm thấy món nào trong menu từ server.")
                 return False
            return True
        else:
            raise Exception(f"Server báo lỗi: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Lỗi Mạng: Không thể tải thực đơn từ server: {e}")
        return False

# --- CÁC HÀM HELPER (Giữ nguyên) ---
# add_to_cart, update_cart_summary, calculate_total_amount,
# get_order_info_string, get_cart_details_text,
# show_menu_screen, show_checkout_screen, show_payment_qr_screen
# ... (Giữ nguyên toàn bộ nội dung các hàm này) ...
def add_to_cart(item_name):
    """Mở keypad số trên màn hình để nhập số lượng."""
    open_quantity_keypad(item_name)
def update_cart_summary():
    """Cập nhật số lượng hiển thị trên icon giỏ hàng."""
    if not shopping_cart:
        render_cart_indicator(0, 0)
        return

    total_items = sum(shopping_cart.values())
    total_amount = calculate_total_amount()
    render_cart_indicator(total_items, total_amount)

def render_cart_indicator(total_items, total_amount):
    """Cập nhật badge giỏ hàng và lưu thông tin tổng."""
    global cart_badge_label, latest_cart_total, cart_drawer
    latest_cart_total = total_amount
    if cart_badge_label:
        display_text = f"{total_items:,}" if total_items > 0 else "0"
        cart_badge_label.configure(text=display_text)
    if cart_drawer and cart_drawer.winfo_exists():
        render_cart_drawer_contents()

def open_cart_drawer():
    """Hiển thị cửa sổ giỏ hàng dạng popover."""
    global cart_drawer, cart_drawer_items_frame, cart_drawer_total_label
    if not root:
        return
    if cart_drawer and cart_drawer.winfo_exists():
        cart_drawer.focus_set()
        return

    cart_drawer = ctk.CTkToplevel(root)
    cart_drawer.title("Giỏ hàng của bạn")
    cart_drawer.geometry("360x520")
    cart_drawer.resizable(False, False)
    cart_drawer.transient(root)
    cart_drawer.grab_set()

    header = ctk.CTkFrame(cart_drawer, fg_color="transparent")
    header.pack(fill="x", padx=16, pady=(16, 8))
    ctk.CTkLabel(header, text="Giỏ hàng", font=(FONT_FAMILY, 20, "bold")).pack(side="left")
    ctk.CTkButton(
        header,
        text="✕",
        width=36,
        height=36,
        fg_color="#E2E8F0",
        text_color=TEXT_PRIMARY,
        hover_color="#CBD5F5",
        command=close_cart_drawer
    ).pack(side="right")

    cart_drawer_items_frame = ctk.CTkScrollableFrame(cart_drawer, fg_color="transparent")
    cart_drawer_items_frame.pack(fill="both", expand=True, padx=16, pady=4)

    footer = ctk.CTkFrame(cart_drawer, fg_color="transparent")
    footer.pack(fill="x", padx=16, pady=16)
    cart_drawer_total_label = ctk.CTkLabel(footer, text="", font=(FONT_FAMILY, 16, "bold"))
    cart_drawer_total_label.pack(anchor="w")

    ctk.CTkButton(
        footer,
        text="Đi tới thanh toán",
        fg_color=SUCCESS_COLOR,
        hover_color="#15803D",
        font=(FONT_FAMILY, 15, "bold"),
        height=48,
        command=lambda: (close_cart_drawer(), show_checkout_screen())
    ).pack(fill="x", pady=(10, 0))

    render_cart_drawer_contents()

def close_cart_drawer():
    """Đóng popover giỏ hàng."""
    global cart_drawer
    if cart_drawer and cart_drawer.winfo_exists():
        cart_drawer.destroy()
    cart_drawer = None

def render_cart_drawer_contents():
    """Vẽ lại danh sách món trong popover."""
    if not cart_drawer_items_frame:
        return
    for widget in cart_drawer_items_frame.winfo_children():
        widget.destroy()

    if not shopping_cart:
        ctk.CTkLabel(
            cart_drawer_items_frame,
            text="Giỏ hàng đang trống.",
            font=(FONT_FAMILY, 14),
            text_color=TEXT_SECONDARY
        ).pack(pady=40)
        if cart_drawer_total_label:
            cart_drawer_total_label.configure(text="Tổng cộng: 0 VND")
        return

    for item_name, quantity in shopping_cart.items():
        price = menu_items[item_name]['price']
        subtotal = price * quantity
        row = ctk.CTkFrame(cart_drawer_items_frame, fg_color="#EEF2FF", corner_radius=12)
        row.pack(fill="x", pady=6)
        ctk.CTkLabel(row, text=item_name, font=(FONT_FAMILY, 13, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w", padx=12, pady=(8, 0))
        detail = ctk.CTkLabel(
            row,
            text=f"{quantity} x {price:,} đ",
            font=(FONT_FAMILY, 12),
            text_color=TEXT_SECONDARY
        )
        detail.pack(anchor="w", padx=12)
        ctk.CTkLabel(
            row,
            text=f"{subtotal:,} đ",
            font=(FONT_FAMILY, 12, "bold"),
            text_color=WARNING_COLOR
        ).pack(anchor="e", padx=12, pady=(0, 8))

    if cart_drawer_total_label:
        cart_drawer_total_label.configure(text=f"Tổng cộng: {latest_cart_total:,} VND")

def calculate_total_amount():
    """Tính tổng tiền từ giỏ hàng."""
    total = 0
    for item, quantity in shopping_cart.items():
        total += menu_items[item]['price'] * quantity
    return total

def get_order_info_string():
    """Tạo chuỗi thông tin đơn hàng (ví dụ: '2x Coca, 1x Pepsi')."""
    if not shopping_cart:
        return "Đơn hàng trống"
    
    parts = [f"{qty}x {item}" for item, qty in shopping_cart.items()]
    return ", ".join(parts)

def get_cart_details_text():
    """Tạo chuỗi chi tiết giỏ hàng cho màn hình thanh toán."""
    if not shopping_cart:
        return "Giỏ hàng trống"

    lines = []
    for item, quantity in shopping_cart.items():
        price = menu_items[item]['price']
        subtotal = price * quantity
        lines.append(f"• {item}: {quantity} x {price:,} = {subtotal:,} VND")
    return "\n".join(lines)

# --- HÀM XỬ LÝ ẢNH ĐA NĂNG (ONLINE + LOCAL) ---
image_cache = {} 

# Trong customer_interface.py, thay thế hàm load_product_image bằng đoạn này:

def load_product_image(image_path):
    """
    Hàm thông minh: Tải ảnh Online (có giả lập trình duyệt) hoặc Offline.
    """
    if not image_path:
        return get_default_image()

    # Kiểm tra Cache
    if image_path in image_cache:
        return image_cache[image_path]

    try:
        pil_image = None
        
        # TRƯỜNG HỢP 1: Link Online (http/https)
        if image_path.startswith("http"):
            print(f"Đang tải ảnh online: {image_path}")
            
            # --- SỬA ĐỔI QUAN TRỌNG: THÊM HEADERS ĐỂ GIẢ LẬP TRÌNH DUYỆT ---
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            # Thêm headers vào request
            response = requests.get(image_path, headers=headers, timeout=5) 
            response.raise_for_status() # Báo lỗi nếu server trả về 403/404
            
            img_data = response.content
            pil_image = Image.open(io.BytesIO(img_data))
            
        # TRƯỜNG HỢP 2: File trên máy tính (Local)
        else:
            if os.path.exists(image_path):
                pil_image = Image.open(image_path)
            else:
                print(f"Không tìm thấy file ảnh: {image_path}")
                return get_default_image()

        # Resize chung
        pil_image = pil_image.resize((120, 120), Image.LANCZOS)
        tk_image = ImageTk.PhotoImage(pil_image)
        
        # Lưu vào cache
        image_cache[image_path] = tk_image
        return tk_image

    except Exception as e:
        print(f"Lỗi xử lý ảnh (Có thể do link bị chặn): {e}")
        return get_default_image()

def get_default_image():
    """Tạo một ô màu xám nếu không có ảnh"""
    if "default" in image_cache: return image_cache["default"]
    
    pil_image = Image.new('RGB', (120, 120), color='#CCCCCC')
    tk_image = ImageTk.PhotoImage(pil_image)
    image_cache["default"] = tk_image
    return tk_image

def create_product_card(parent_frame, item_name, price,image_url, row, col):
    """Tạo card món với phong cách kiosk hiện đại."""
    card = ctk.CTkFrame(
        parent_frame,
        fg_color=CARD_BG_COLOR,
        border_color=HIGHLIGHT_COLOR,
        border_width=1,
        corner_radius=16
    )
    card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

    img = load_product_image(image_url)
    img_label = ctk.CTkLabel(card, image=img, text="", fg_color="transparent", cursor="hand2")
    img_label.pack(pady=(10, 8))
    img_label.image = img

    name_label = ctk.CTkLabel(
        card,
        text=item_name,
        font=(FONT_FAMILY, 14, "bold"),
        text_color=TEXT_PRIMARY,
        wraplength=150,
        justify="center",
        cursor="hand2"
    )
    name_label.pack(padx=8)

    price_badge = ctk.CTkLabel(
        card,
        text=f"{price:,} đ",
        font=(FONT_FAMILY, 13, "bold"),
        fg_color="#DCFCE7",
        text_color=SUCCESS_COLOR,
        corner_radius=12,
        padx=14,
        pady=4,
        cursor="hand2"
    )
    price_badge.pack(pady=(6, 12))

    def on_click(_event):
        add_to_cart(item_name)

    for widget in (card, img_label, name_label, price_badge):
        widget.bind("<Button-1>", on_click)

    return card

def prompt_quantity(item_name):
    """Hiển thị ô nhập số lượng dạng InputDialog."""
    if not root:
        return None
    dialog = ctk.CTkInputDialog(
        text=f"Nhập số lượng cho {item_name}:",
        title="Số lượng"
    )
    try:
        dialog._entry.delete(0, "end")
    except Exception:
        pass
    result = dialog.get_input()
    if result is None:
        return None
    result = result.strip()
    if not result:
        messagebox.showwarning("Lỗi", "Vui lòng nhập số.")
        return None
    try:
        quantity = int(result)
        if quantity <= 0:
            raise ValueError
        return quantity
    except ValueError:
        messagebox.showerror("Lỗi", "Số lượng phải là số nguyên > 0.")
        return None

def show_toast(message, duration=2000):
    """Hiển thị thông báo ngắn gọn ở cuối màn hình."""
    global toast_label
    if not root:
        return
    if toast_label and toast_label.winfo_exists():
        toast_label.destroy()
    toast_label = ctk.CTkLabel(
        root,
        text=message,
        fg_color="#111827",
        text_color="white",
        corner_radius=20,
        font=(FONT_FAMILY, 14, "bold"),
        padx=16,
        pady=10
    )
    toast_label.place(relx=0.5, rely=0.97, anchor="s")
    root.after(duration, lambda: toast_label.destroy() if toast_label and toast_label.winfo_exists() else None)

def build_order_success_message(prefix="Đơn hoàn tất"):
    """Tạo thông báo tóm tắt đơn hàng."""
    if not shopping_cart:
        return prefix
    total_items = sum(shopping_cart.values())
    items_text = ", ".join([f"{qty} {item}" for item, qty in shopping_cart.items()])
    return f"{prefix}: {total_items} món ({items_text})"

def open_quantity_keypad(item_name):
    """Hiển thị keypad số lớn để chọn số lượng trên màn hình."""
    if not root:
        return

    dialog = ctk.CTkToplevel(root)
    dialog.title(f"Số lượng {item_name}")
    dialog.geometry("320x420")
    dialog.resizable(False, False)
    dialog.transient(root)
    dialog.grab_set()

    qty_var = ctk.StringVar(value="")

    ctk.CTkLabel(
        dialog,
        text=f"Nhập số lượng cho\n{item_name}",
        font=(FONT_FAMILY, 16, "bold"),
        text_color=TEXT_PRIMARY
    ).pack(pady=(16, 4))

    display = ctk.CTkLabel(
        dialog,
        textvariable=qty_var,
        font=(FONT_FAMILY, 32, "bold"),
        fg_color=CARD_BG_COLOR,
        text_color=ACCENT_COLOR,
        corner_radius=12,
        width=160,
        height=60
    )
    display.pack(pady=(4, 12))

    grid = ctk.CTkFrame(dialog, fg_color="transparent")
    grid.pack(pady=4)

    def append_digit(d):
        cur = qty_var.get()
        if len(cur) >= 3:
            return
        qty_var.set(cur + str(d))

    def clear_qty():
        qty_var.set("")

    def confirm():
        text = qty_var.get().strip()
        if not text:
            messagebox.showwarning("Lỗi", "Vui lòng nhập số lượng.")
            return
        try:
            q = int(text)
            if q <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Lỗi", "Số lượng phải là số nguyên > 0.")
            clear_qty()
            return
        shopping_cart[item_name] = shopping_cart.get(item_name, 0) + q
        update_cart_summary()
        show_toast(f"Đã thêm {q} {item_name} vào giỏ hàng")
        dialog.destroy()

    buttons = [
        ("1", lambda: append_digit(1)), ("2", lambda: append_digit(2)), ("3", lambda: append_digit(3)),
        ("4", lambda: append_digit(4)), ("5", lambda: append_digit(5)), ("6", lambda: append_digit(6)),
        ("7", lambda: append_digit(7)), ("8", lambda: append_digit(8)), ("9", lambda: append_digit(9)),
        ("Xóa", clear_qty), ("0", lambda: append_digit(0)), ("OK", confirm),
    ]

    for index, (label, cmd) in enumerate(buttons):
        r, c = divmod(index, 3)
        btn = ctk.CTkButton(
            grid,
            text=label,
            width=70,
            height=56,
            fg_color=SUCCESS_COLOR if label == "OK" else ("#FACC15" if label == "Xóa" else "#E5E7EB"),
            text_color="white" if label in ("OK", "Xóa") else TEXT_PRIMARY,
            font=(FONT_FAMILY, 16, "bold"),
            command=cmd
        )
        btn.grid(row=r, column=c, padx=4, pady=4, sticky="nsew")

    for i in range(3):
        grid.grid_columnconfigure(i, weight=1)

    ctk.CTkButton(
        dialog,
        text="Hủy",
        fg_color=DANGER_COLOR,
        hover_color="#B91C1C",
        font=(FONT_FAMILY, 14, "bold"),
        width=100,
        command=dialog.destroy
    ).pack(pady=(8, 12))
def show_menu_screen():
    """Hiển thị màn hình chọn món."""
    status_label.configure(text="Mời bạn chọn đồ uống", text_color="white")
    
    if checkout_frame:
        checkout_frame.pack_forget()
    if payment_frame:
        payment_frame.pack_forget()
        
    menu_frame.pack(fill="both", expand=True)
    update_cart_summary()

def show_idle_screen():
    """Hiển thị màn hình chờ thân thiện."""
    global status_label, is_busy
    
    is_busy = False # Đánh dấu là robot đang rảnh
    
    # Ẩn tất cả các frame phục vụ
    if menu_frame: menu_frame.pack_forget()
    if checkout_frame: checkout_frame.pack_forget()
    if payment_frame: payment_frame.pack_forget()
    
    # Cập nhật trạng thái
    if status_label:
        status_label.configure(text="🤖 Robot đang chờ lệnh phục vụ...", text_color="lightgreen")
    
    # Hiển thị frame chờ
    if idle_frame:
        idle_frame.pack(fill="both", expand=True)

# --- HÀM POLLING MỚI (THAY THẾ robot_idle_loop CŨ) ---
def check_for_new_orders():
    """
    Hàm này sẽ chạy liên tục mỗi 5 giây nhờ root.after
    để kiểm tra xem có đơn hàng mới không.
    """
    global is_busy, CURRENT_TABLE, CURRENT_SERVICE_REQUEST_ID
    
    # Nếu đang phục vụ khách, thì KHÔNG kiểm tra đơn mới (để tránh xung đột)
    if is_busy:
        root.after(5000, check_for_new_orders) # Gọi lại sau 5s
        return

    print(f"[{time.strftime('%H:%M:%S')}] Đang kiểm tra lệnh gọi phục vụ...", end='\r')
    
    try:
        url = f"{HEROKU_APP_URL}/api/get-service-requests"
        response = requests.get(url, timeout=5)
        
        if response.status_code == 200:
            requests_list = response.json()
            
            if requests_list:
                # --- TÌM THẤY LỆNH MỚI ---
                service_req = requests_list[0]
                CURRENT_TABLE = service_req.get('table_number')
                CURRENT_SERVICE_REQUEST_ID = service_req.get('request_id')
                
                print(f"\n🔔 CÓ LỆNH MỚI! Bàn {CURRENT_TABLE}")
                
                # Báo server đã nhận
                try:
                    requests.post(f"{HEROKU_APP_URL}/api/complete-service-request/{CURRENT_SERVICE_REQUEST_ID}", timeout=5)
                except:
                    pass
                
                # CHUYỂN SANG CHẾ ĐỘ PHỤC VỤ
                start_serving_customer() 
                return # Thoát hàm để dừng poll tạm thời, chờ lệnh phục vụ xong
                
    except Exception as e:
        print(f"\nLỗi kết nối: {e}")

    # Lên lịch chạy lại hàm này sau 5000ms (5 giây)
    if root:
        root.after(5000, check_for_new_orders)

# --- HÀM BẮT ĐẦU PHỤC VỤ (MỚI) ---
def start_serving_customer():
    global is_busy, shopping_cart, current_orderId, conversation_history
    
    is_busy = True # Đánh dấu đang bận
    idle_frame.pack_forget() # Ẩn màn hình chờ
    
    # Reset dữ liệu
    shopping_cart = {}
    current_orderId = None
    
    # Setup lại ngữ cảnh AI
    menu_string = ", ".join([f"{name}" for name in menu_items.keys()])
    chat_system_prompt = (f"Bạn là robot phục vụ Bàn {CURRENT_TABLE}. Menu: {menu_string}.")
    conversation_history = [{"role": "system", "content": chat_system_prompt}]
    
    # Chào khách
    speak(f"Xin chào bàn số {CURRENT_TABLE}, tôi đã đến rồi đây.")
    
    # Hiện menu
    show_menu_screen()
    
    # Tiếp tục vòng lặp kiểm tra đơn (nhưng nó sẽ bị chặn bởi if is_busy)
    root.after(5000, check_for_new_orders)


def show_checkout_screen():
    """Hiển thị màn hình chọn phương thức thanh toán."""
    if not shopping_cart:
        messagebox.showwarning("Lỗi", "Giỏ hàng của bạn đang trống!")
        return
        
    status_label.configure(text="Xác nhận đơn hàng và thanh toán", text_color="white")

    menu_frame.pack_forget()
    payment_frame.pack_forget()
        
    checkout_details_label.configure(text=get_cart_details_text())
    if checkout_total_label:
        checkout_total_label.configure(text=f"Tổng cộng: {calculate_total_amount():,} VND")
    
    checkout_frame.pack(fill="both", expand=True)

def show_payment_qr_screen():
    """Hiển thị màn hình quét mã QR."""
    status_label.configure(text="Quét mã để thanh toán", text_color="white")
    
    menu_frame.pack_forget()
    checkout_frame.pack_forget()
        
    payment_frame.pack(fill="both", expand=True)


# --- HÀM MỚI: KẾT THÚC VÀ QUAY VỀ CHỜ ---
# --- SỬA LẠI HÀM finish_and_go_home ---
def finish_and_go_home():
    """Thay vì đóng cửa sổ, ta chỉ quay về màn hình chờ."""
    print("Kết thúc phiên, quay về màn hình chờ.")
    show_idle_screen()
    # KHÔNG GỌI threading.Thread Ở ĐÂY NỮA!

# --- HÀM XỬ LÝ THANH TOÁN (MODIFIED) ---

def handle_qr_payment():
    """MODIFIED: Xử lý khi nhấn nút 'Thanh toán QR'."""
    global CURRENT_TABLE
    print("Bắt đầu thanh toán QR...")
    show_payment_qr_screen()
    
    total_amount = str(calculate_total_amount())
    order_info = get_order_info_string()
    
    # MODIFIED: Gửi kèm số bàn
    start_payment(total_amount, order_info, CURRENT_TABLE)

def handle_cash_payment():
    """MODIFIED: Xử lý khi nhấn nút 'Thanh toán tại quầy'."""
    global CURRENT_TABLE
    print("Bắt đầu gửi đơn hàng tiền mặt...")

    order_info = get_order_info_string()
    total_amount = calculate_total_amount()

    status_label.configure(text="Đang gửi đơn hàng, vui lòng chờ...", text_color="blue")
    root.update_idletasks()

    try:
        url = f"{HEROKU_APP_URL}/api/create-cash-order"
        payload = {
            'info': order_info,
            'amount': total_amount,
            'table': CURRENT_TABLE # <-- MODIFIED: Gửi kèm số bàn
        }
        response = requests.post(url, json=payload, timeout=10)

        if response.status_code == 201:
            messagebox.showinfo(
                "Đã gửi đơn hàng",
                f"Đã gửi đơn hàng tới quầy.\nVui lòng đến quầy để thanh toán số tiền: {total_amount:,} VND"
            )
            # MODIFIED: Quay về chế độ chờ
            finish_and_go_home()
        else:
            raise Exception(f"Server báo lỗi: {response.json().get('error', 'Lỗi không xác định')}")

    except Exception as e:
        print(f"Lỗi khi tạo đơn tiền mặt: {e}")
        messagebox.showerror("Lỗi", f"Không thể gửi đơn hàng: {e}")
        show_checkout_screen()
# --- SỬA LẠI HÀM start_payment ĐỂ DÙNG SEPAY/VIETQR ---

def start_payment(amount, info, table):
    global current_orderId, root, qr_label
    
    status_label.configure(text="Đang tạo mã VietQR...", text_color="blue")
    root.update_idletasks() 
    
    try:
        # Gọi API mới của Server (không còn liên quan MoMo)
        print(f"Yêu cầu tạo thanh toán: {amount}VND - Bàn {table}")
        
        # URL gọi API create-payment
        url = f"{HEROKU_APP_URL}/create-payment?amount={amount}&info={info}&table={table}"
        response = requests.get(url, timeout=10)
        
        if response.status_code != 200:
            raise Exception(f"Server báo lỗi: {response.text}")
        
        data = response.json()
        
        # Server trả về { 'orderId': 'DH12345', 'payUrl': 'https://img.vietqr.io/...' }
        current_orderId = data.get('orderId')
        qr_image_url = data.get('payUrl')
        
        if not current_orderId or not qr_image_url:
            raise Exception("Dữ liệu từ server không hợp lệ (thiếu ID hoặc Link ảnh).")

        print(f"Đã nhận Order ID: {current_orderId}")
        print(f"Link VietQR: {qr_image_url}")

        # Tải ảnh QR từ link VietQR về
        # Lưu ý: Cần thêm User-Agent để VietQR không chặn
        headers = {'User-Agent': 'Mozilla/5.0'}
        qr_response = requests.get(qr_image_url, headers=headers, timeout=10)
        
        # Xử lý ảnh để hiển thị lên giao diện Tkinter
        img_data = qr_response.content
        pil_image = Image.open(io.BytesIO(img_data))
        pil_image = pil_image.resize((300, 400), Image.LANCZOS) # Kích thước chuẩn cho frame
        qr_photo = ImageTk.PhotoImage(pil_image)
        
        # Cập nhật giao diện
        qr_label.configure(image=qr_photo)
        qr_label.image = qr_photo # Giữ tham chiếu ảnh
        
        # Hiển thị hướng dẫn
        msg_text = f"QUÉT MÃ ĐỂ THANH TOÁN\nNội dung CK: {current_orderId}"
        status_label.configure(text=msg_text, text_color="red")
        speak(f"Mời bạn quét mã QR. Hệ thống sẽ tự động xác nhận khi nhận được tiền.")
        
        # Bắt đầu vòng lặp kiểm tra trạng thái
        root.after(3000, poll_for_payment)

    except Exception as e:
        print(f"Lỗi tạo QR: {e}")
        messagebox.showerror("Lỗi", f"Không thể tạo mã thanh toán: {e}")
        reset_kiosk()

def poll_for_payment():
    """
    MODIFIED: Khi thanh toán thành công, quay về chế độ chờ.
    """
    global current_orderId, root
    if not current_orderId: return
    try:
        url = f"{HEROKU_APP_URL}/check-status?orderId={current_orderId}"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            raise Exception("Server Heroku không phản hồi.")
        status = response.json().get('status')
        print(f"Trạng thái nhận được: {status}")

        if status == 'paid':
            print("THANH TOÁN THÀNH CÔNG!")
            status_label.configure(text="Thanh toán thành công! Mời bạn đợi...", text_color="green")
            qr_label.configure(image=None)
            qr_label.image = None
            
            # MODIFIED: Quay về chế độ chờ sau 5 giây
            root.after(5000, finish_and_go_home) 
            
        elif status == 'pending':
            root.after(3000, poll_for_payment)
        else:
            raise Exception("Thanh toán thất bại hoặc không tìm thấy.")
    except Exception as e:
        print(f"Lỗi polling: {e}")
        messagebox.showerror("Lỗi", f"Lỗi khi kiểm tra thanh toán: {e}")
        reset_kiosk() # Nếu lỗi thì reset về menu
# --- HÀM QUẢN LÝ GIAO DIỆN ---
def reset_kiosk():
    """
    MODIFIED: Reset giao diện VÀ giỏ hàng.
    Hàm này giờ chỉ quay về menu (trong trường hợp khách HỦY).
    """
    global current_orderId, shopping_cart
    print("Resetting Kiosk (quay về menu)...")
    current_orderId = None
    shopping_cart = {}
    if qr_label:
        qr_label.configure(image=None)
        qr_label.image = None
    close_cart_drawer()
    show_menu_screen()

# --- CÁC HÀM VOICE (Giữ nguyên) ---
# speak, listen, get_openai_response,
# process_voice_command, start_voice_thread, voice_loop
# ... (Giữ nguyên toàn bộ nội dung các hàm này) ...
def speak(text):
    """Chuyển văn bản thành giọng nói (OpenAI TTS) và phát bằng pygame.Sound."""
    global status_label
    print(f"🤖 Robot: {text}")
    # Đảm bảo root đã tồn tại trước khi gọi .after
    if root:
        root.after(0, lambda: status_label.configure(text=f"Robot: {text}", text_color="white"))
    try:
        filename = "voice_order_response.mp3"
        with client.audio.speech.with_streaming_response.create(
            model="tts-1",
            voice="alloy",
            input=text
        ) as response:
            response.stream_to_file(filename)
        sound = pygame.mixer.Sound(filename)
        sound.play()
        pygame.time.wait(int(sound.get_length() * 1000))
        os.remove(filename)
    except Exception as e:
        print(f"❌ Lỗi khi chuyển văn bản thành giọng nói: {e}")
        if root:
            root.after(0, lambda: status_label.configure(text=f"Lỗi phát âm thanh: {e}", text_color="#F87171"))

def listen():
    """Nghe từ micro và trả về văn bản."""
    global status_label, recognizer
    with sr.Microphone() as source:
        if root: root.after(0, lambda: status_label.configure(text="🎧 Đang nghe...", text_color="white"))
        print("🎧 Đang nghe...")
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            if root: root.after(0, lambda: status_label.configure(text="Đang xử lý...", text_color="#CBD5F5"))
            text = recognizer.recognize_google(audio, language="vi-VN")
            print(f"👤 Bạn: {text}")
            if root: root.after(0, lambda: status_label.configure(text=f"Bạn: {text}", text_color="white"))
            return text.lower()
        except sr.WaitTimeoutError:
            if root: root.after(0, lambda: status_label.configure(text="Không phát hiện được giọng nói.", text_color="#CBD5F5"))
            return None
        except sr.UnknownValueError:
            speak("Xin lỗi, tôi không nghe rõ.")
            return None
        except sr.RequestError:
            speak("Lỗi kết nối dịch vụ nhận dạng giọng nói.")
            return None
def get_openai_response(user_input):
    """
    Hàm MỚI: Gửi câu hỏi đến OpenAI và lấy câu trả lời.
    """
    global conversation_history
    conversation_history.append({"role": "user", "content": user_input})
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=conversation_history,
            temperature=0.7,
            max_tokens=500,
        )
        ai_response = response.choices[0].message.content.strip()
        conversation_history.append({"role": "assistant", "content": ai_response})
        return ai_response
    except Exception as e:
        print(f"Lỗi khi gọi API: {e}")
        conversation_history.pop()
        return "Tôi đang gặp một chút sự cố, bạn vui lòng thử lại sau nhé."
def process_voice_command(text):
    """
    Phân tích câu nói của người dùng:
    1. Ưu tiên các hành động (đặt món, thanh toán, xóa).
    2. Nếu không phải, chuyển sang cho AI (OpenAI) trả lời.
    """
    global shopping_cart, menu_items
    text_lower = text.lower()
    # --- 1. LOGIC PHÁT NHẠC (MỚI THÊM) ---
    # Kiểm tra xem câu nói có chứa cụm từ khóa không
    if "biết ông thương không" in text_lower:
        speak("Dạ biết chứ, để em mở cho anh nghe nè.")
        # Đợi robot nói xong câu trên rồi mới mở nhạc (khoảng 2 giây)
        if root:
            root.after(2000, lambda: play_music_file(r"D:\AI_VoiceChat\Re_Robot\Kiosk_Robot\know_thuong.mp3")) # <-- Tên file nhạc của bạn
        return

    if "dừng nhạc" in text_lower or "tắt nhạc" in text_lower:
        pygame.mixer.music.stop()
        speak("Đã tắt nhạc.")
        return
    
    num_map = {"một": 1, "hai": 2, "ba": 3, "bốn": 4, "năm": 5}
    
    if "thanh toán" in text_lower:
        speak("Vâng, chuyển đến màn hình thanh toán.")
        root.after(10, show_checkout_screen)
        return
    if "xóa giỏ hàng" in text_lower or "làm lại" in text_lower or "hủy đơn" in text_lower:
        speak("Đã xóa giỏ hàng. Mời bạn chọn lại.")
        root.after(10, reset_kiosk)
        return

    found_items = {}
    words = text_lower.split()
    current_qty = 1
    for i, word in enumerate(words):
        if word in num_map:
            current_qty = num_map[word]
        elif word.isdigit():
            current_qty = int(word)
        possible_item_1 = word
        possible_item_2 = " ".join(words[i:i+2])
        for item_name in menu_items.keys():
            item_lower = item_name.lower()
            if item_lower == possible_item_2:
                found_items[item_name] = current_qty
                current_qty = 1 
                break 
            elif item_lower == possible_item_1:
                found_items[item_name] = current_qty
                current_qty = 1
                break
    if found_items:
        items_spoken = []
        for item, qty in found_items.items():
            shopping_cart[item] = shopping_cart.get(item, 0) + qty
            items_spoken.append(f"{qty} {item}")
        speak_text = f"Đã thêm {', '.join(items_spoken)} vào giỏ hàng."
        speak(speak_text)
        root.after(10, update_cart_summary)
        return
    else:
        print("Không tìm thấy lệnh đặt hàng, chuyển sang OpenAI...")
        if root: root.after(0, lambda: status_label.configure(text="Vâng, để tôi suy nghĩ...", text_color="#93C5FD"))
        ai_response = get_openai_response(text)
        speak(ai_response)
        
def start_voice_thread():
    """Bắt đầu luồng lắng nghe (được gọi bởi nút bấm)."""
    global voice_button
    if voice_button: voice_button.configure(state="disabled", text="...")
    threading.Thread(target=voice_loop, daemon=True).start()
    
def voice_loop():
    """
    Hàm này chạy trong Thread. 
    Nó lắng nghe, sau đó xử lý, rồi kích hoạt lại nút.
    """
    text = listen()
    if text:
        process_voice_command(text)
    if root and voice_button: 
        root.after(10, lambda: voice_button.configure(state="normal", text="🎙️ Nhấn để nói"))

def play_music_file(filename):
    """Hàm chuyên dùng để phát nhạc (không chặn giao diện)."""
    try:
        if not os.path.exists(filename):
            speak("Xin lỗi, tôi không tìm thấy file nhạc.")
            return

        # Dừng nhạc hoặc giọng nói đang phát (nếu có)
        if pygame.mixer.music.get_busy():
            pygame.mixer.music.stop()

        # Load và phát nhạc
        pygame.mixer.music.load(filename)
        pygame.mixer.music.play()
        
        # Không dùng pygame.time.wait() ở đây để Robot vẫn hoạt động được
        # trong lúc nhạc đang chạy nền.
        print(f"Đang phát nhạc: {filename}")
        
    except Exception as e:
        print(f"Lỗi phát nhạc: {e}")
        speak("Có lỗi khi mở nhạc.")

def main():
    # 1. Khai báo toàn bộ biến Global cần dùng
    global root, status_label, menu_frame, checkout_frame, payment_frame, idle_frame
    global cart_badge_label
    global checkout_details_label, checkout_total_label, qr_label
    global voice_button
    global conversation_history, chat_system_prompt
    global shopping_cart, current_orderId, menu_items
    
    # 2. Tạo cửa sổ chính (Chỉ chạy 1 lần)
    root = ctk.CTk()
    root.title("ROBOT PHỤC VỤ - HỆ THỐNG TỰ ĐỘNG")
    root.geometry("520x860")
    root.minsize(480, 780)
    root.configure(fg_color=APP_BG_COLOR)
    # root.attributes('-fullscreen', True)

    # 3. Tải Menu ngay khi khởi động
    if not load_menu_from_server():
        print("Cảnh báo: Không tải được menu lúc khởi động. Sẽ thử lại sau.")

    # --- LABEL TRẠNG THÁI CHUNG ---
    status_label = ctk.CTkLabel(
        root,
        text="Hệ thống sẵn sàng",
        font=(FONT_FAMILY, 13, "bold"),
        fg_color="#0F172A",
        text_color="white",
        pady=10,
        corner_radius=0
    )
    status_label.pack(side="bottom", fill="x")

    content_wrapper = ctk.CTkFrame(root, fg_color=APP_BG_COLOR)
    content_wrapper.pack(fill="both", expand=True)

    # --- TẠO MÀN HÌNH CHỜ (IDLE FRAME) ---
    idle_frame = ctk.CTkFrame(content_wrapper, fg_color=APP_BG_COLOR)
    hero = ctk.CTkFrame(idle_frame, fg_color=CARD_BG_COLOR, border_color=HIGHLIGHT_COLOR, border_width=1, corner_radius=24)
    hero.pack(padx=40, pady=80, fill="both", expand=True)
    ctk.CTkLabel(hero, text="🤖", font=("Arial", 70), fg_color="transparent").pack(pady=(30, 10))
    ctk.CTkLabel(hero, text="XIN CHÀO!", font=(FONT_FAMILY, 30, "bold"), text_color=ACCENT_COLOR).pack()
    ctk.CTkLabel(
        hero,
        text="Robot đang sẵn sàng phục vụ.\nHãy chọn đồ uống để bắt đầu.",
        font=(FONT_FAMILY, 14),
        text_color=TEXT_SECONDARY,
        justify="center"
    ).pack(pady=20)

    # ============================================================
    # KHỞI TẠO SẴN CÁC FRAME PHỤC VỤ
    # ============================================================

    # --- 1. MÀN HÌNH MENU (MENU FRAME) ---
    menu_frame = ctk.CTkFrame(content_wrapper, fg_color=APP_BG_COLOR)

    header = ctk.CTkFrame(menu_frame, fg_color=APP_BG_COLOR)
    header.pack(fill="x", padx=24, pady=(16, 6))

    title_block = ctk.CTkFrame(header, fg_color=APP_BG_COLOR)
    title_block.pack(fill="x", anchor="w")
    ctk.CTkLabel(title_block, text="Mời bạn chọn đồ uống", font=(FONT_FAMILY, 22, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w")
    ctk.CTkLabel(title_block, text="Chạm vào card món để thêm vào giỏ hàng", font=(FONT_FAMILY, 12), text_color=TEXT_SECONDARY).pack(anchor="w", pady=(4, 0))

    icon_block = ctk.CTkFrame(header, fg_color=APP_BG_COLOR)
    icon_block.pack(anchor="e", pady=(0,0))
    cart_button = ctk.CTkButton(
        icon_block,
        text="🛒",
        width=65,
        height=65,
        fg_color=ACCENT_COLOR,
        hover_color="#1D4ED8",
        font=(FONT_FAMILY, 26),
        command=open_cart_drawer
    )
    cart_button.pack()
    cart_badge_label = ctk.CTkLabel(
        icon_block,
        text="0",
        font=(FONT_FAMILY, 14, "bold"),
        fg_color="#FACC15",
        bg_color=ACCENT_COLOR,
        text_color="#1F2937",
        corner_radius=999,
        width=36,
        height=24
    )
    cart_badge_label.place(relx=1, rely=0, anchor="ne", x=6, y=-6)
    render_cart_indicator(0, 0)
    
    button_grid_frame = ctk.CTkScrollableFrame(menu_frame, fg_color=APP_BG_COLOR)
    button_grid_frame.pack(fill="both", expand=True, padx=10, pady=(0, 5))

    MAX_COLUMNS = 2 
    current_row = 0
    current_col = 0
    item_list = list(menu_items.keys())

    # --- VÒNG LẶP TẠO THẺ SẢN PHẨM (Card) ---
    for item_name in item_list:
        item_data = menu_items[item_name] 
        price = item_data['price']
        img_url = item_data.get('image_url', "")
        
        if not img_url:
            for ext in [".png", ".jpg", ".jpeg"]:
                if os.path.exists(f"assets/{item_name}{ext}"):
                    img_url = f"assets/{item_name}{ext}"
                    break
        
        create_product_card(button_grid_frame, item_name, price, img_url, current_row, current_col)
        
        current_col += 1
        if current_col >= MAX_COLUMNS:
            current_col = 0
            current_row += 1

    for i in range(MAX_COLUMNS):
        button_grid_frame.grid_columnconfigure(i, weight=1)

    action_frame = ctk.CTkFrame(menu_frame, fg_color=APP_BG_COLOR)
    action_frame.pack(fill="x", padx=24, pady=(0, 18))
    
    checkout_btn = ctk.CTkButton(
        action_frame,
        text="Thanh toán ngay",
        fg_color=SUCCESS_COLOR,
        hover_color="#15803D",
        font=(FONT_FAMILY, 16, "bold"),
        height=52,
        corner_radius=999,
        command=show_checkout_screen
    )
    checkout_btn.pack(pady=10, fill="x")
    
    voice_button = ctk.CTkButton(
        action_frame,
        text="🎙️ Nhấn để nói",
        fg_color=ACCENT_COLOR,
        hover_color="#1D4ED8",
        font=(FONT_FAMILY, 15, "bold"),
        height=50,
        command=start_voice_thread
    )
    voice_button.pack(fill="x", pady=(0, 6))

    # --- 2. MÀN HÌNH THANH TOÁN (CHECKOUT FRAME) ---
    checkout_frame = ctk.CTkFrame(content_wrapper, fg_color=APP_BG_COLOR)
    ctk.CTkLabel(checkout_frame, text="Xác nhận đơn hàng và thanh toán", font=(FONT_FAMILY, 26, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w", padx=32, pady=(32, 6))
    ctk.CTkLabel(checkout_frame, text="Kiểm tra chi tiết đơn trước khi chọn phương thức", font=(FONT_FAMILY, 13), text_color=TEXT_SECONDARY).pack(anchor="w", padx=32, pady=(0, 18))

    summary_card = ctk.CTkFrame(checkout_frame, fg_color=CARD_BG_COLOR, border_color="#D0D7E3", border_width=1, corner_radius=26)
    summary_card.pack(fill="x", padx=32, pady=10)

    ctk.CTkLabel(summary_card, text="Chi tiết đơn hàng", font=(FONT_FAMILY, 15, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w", padx=20, pady=(18, 6))
    checkout_details_label = ctk.CTkLabel(
        summary_card,
        text="...",
        font=(FONT_FAMILY, 15),
        justify="left",
        text_color="#1F2937",
        anchor="w"
    )
    checkout_details_label.pack(fill="x", padx=20, pady=(0, 12))
    ctk.CTkLabel(summary_card, text="", height=1, fg_color=HIGHLIGHT_COLOR).pack(fill="x", padx=20, pady=(0, 18))
    checkout_total_label = ctk.CTkLabel(summary_card, text="Tổng cộng: 0 VND", font=(FONT_FAMILY, 17, "bold"), text_color=ACCENT_COLOR)
    checkout_total_label.pack(anchor="e", padx=20, pady=(0, 24))
    
    button_stack = ctk.CTkFrame(checkout_frame, fg_color=APP_BG_COLOR)
    button_stack.pack(pady=20, fill="x", padx=32)

    btn_qr = ctk.CTkButton(
        button_stack,
        text="Thanh toán QR (Tự động)",
        fg_color="#7C3AED",
        hover_color="#6D28D9",
        font=(FONT_FAMILY, 17, "bold"),
        height=60,
        corner_radius=20,
        command=handle_qr_payment
    )
    btn_qr.pack(pady=12, fill="x")

    btn_cash = ctk.CTkButton(
        button_stack,
        text="Thanh toán tại quầy",
        fg_color="#0F766E",
        hover_color="#0D4D4A",
        font=(FONT_FAMILY, 17, "bold"),
        height=60,
        corner_radius=20,
        command=handle_cash_payment
    )
    btn_cash.pack(pady=12, fill="x")

    btn_back = ctk.CTkButton(
        button_stack,
        text="Quay lại chọn món",
        fg_color="#F97316",
        hover_color="#EA580C",
        font=(FONT_FAMILY, 16, "bold"),
        height=54,
        corner_radius=20,
        command=show_menu_screen
    )
    btn_back.pack(pady=16, fill="x")

    # --- 3. MÀN HÌNH QUÉT MÃ (PAYMENT FRAME) ---
    payment_frame = ctk.CTkFrame(content_wrapper, fg_color=APP_BG_COLOR)
    ctk.CTkLabel(payment_frame, text="Quét mã để thanh toán", font=(FONT_FAMILY, 22, "bold"), text_color=TEXT_PRIMARY).pack(anchor="w", padx=24, pady=(24, 4))
    ctk.CTkLabel(payment_frame, text="Mở app ngân hàng hoặc ví điện tử để quét mã QR", font=(FONT_FAMILY, 12), text_color=TEXT_SECONDARY).pack(anchor="w", padx=24, pady=(0, 10))

    qr_card = ctk.CTkFrame(payment_frame, fg_color=CARD_BG_COLOR, border_color=HIGHLIGHT_COLOR, border_width=1, corner_radius=18)
    qr_card.pack(padx=30, pady=20)
    qr_label = ctk.CTkLabel(qr_card, text="", fg_color=CARD_BG_COLOR)
    qr_label.pack(padx=20, pady=20)
    
    btn_cancel = ctk.CTkButton(
        payment_frame,
        text="Hủy bỏ",
        fg_color=DANGER_COLOR,
        hover_color="#B91C1C",
        font=(FONT_FAMILY, 14, "bold"),
        width=200,
        command=reset_kiosk
    )
    btn_cancel.pack(pady=20)

    # ============================================================
    # BẮT ĐẦU CHƯƠNG TRÌNH
    # ============================================================
    
    show_idle_screen()
    check_for_new_orders()
    
    print("🚀 Hệ thống Robot đã khởi động. Đang chờ lệnh...")
    root.mainloop()

# --- HÀM MỚI: VÒNG LẶP CHỜ CỦA ROBOT ---
# --- SỬA HÀM NÀY ---
def robot_idle_loop():
    print("🤖 Robot đang ở chế độ chờ, bắt đầu poll API...")
    
    if not load_menu_from_server():
        print("Không tải được menu, thử lại sau...")
    
    while True: # Vòng lặp vô tận trên MAIN THREAD
        try:
            # ... (Phần gọi API giữ nguyên) ...
            url = f"{HEROKU_APP_URL}/api/get-service-requests"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                requests_list = response.json()
                
                if requests_list:
                    service_req = requests_list[0]
                    table = service_req.get('table_number')
                    req_id = service_req.get('request_id')
                    
                    print(f"🔔 CÓ LỆNH MỚI! Đi đến Bàn {table}")
                    
                    # Báo cáo đã nhận lệnh (Giữ nguyên code của bạn)
                    try:
                        requests.post(f"{HEROKU_APP_URL}/api/complete-service-request/{req_id}", timeout=5)
                    except:
                        pass
                    
                    # --- KHỞI ĐỘNG GIAO DIỆN ---
                    print("Mở giao diện phục vụ...")
                    
                    # Hàm main() sẽ chạy và CHẶN (block) tại đây cho đến khi finish_and_go_home() được gọi
                    main(table_number=table, request_id=req_id)
                    
                    # KHI main() KẾT THÚC (do finish_and_go_home đóng cửa sổ), code sẽ chạy tiếp xuống đây
                    print("Giao diện đã đóng. Robot quay lại trạng thái chờ (Idle)...")
                    
                    # Vòng lặp while True sẽ tự động lặp lại -> Poll tiếp
                    
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Đang chờ khách gọi...", end='\r')
                    time.sleep(5)
            else:
                time.sleep(5)
                
        except Exception as e:
            print(f"Lỗi trong vòng lặp chờ: {e}")
            time.sleep(10)


# --- MODIFIED: ĐIỂM BẮT ĐẦU CỦA CHƯƠNG TRÌNH ---
if __name__ == "__main__":
    main()