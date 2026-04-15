import customtkinter as ctk
from firebase_config import db
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime

from intake_module import IntakeModule
from sales_module import SalesModule
from order_manager_module import OrderManagerModule

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class MainApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("PRO Cosmetic IMS - Master Hub")
        self.geometry("1400x900")

        self.container = ctk.CTkFrame(self)
        self.container.pack(side="top", fill="both", expand=True)
        
        self.show_main_menu()

    def clear_screen(self):
        for widget in self.container.winfo_children():
            widget.destroy()

    def show_main_menu(self):
        self.clear_screen()
        
        ctk.CTkLabel(self.container, text="Cosmetic Management System", font=("Arial", 28, "bold")).pack(pady=40)
        
        btn_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        btn_frame.pack(pady=20)

        # Row 0: Intake
        ctk.CTkButton(btn_frame, text="New Global Order", height=60, width=250, command=lambda: self.launch_module("Intake", "Global")).grid(row=0, column=0, padx=20, pady=10)
        ctk.CTkButton(btn_frame, text="New Local Order", height=60, width=250, command=lambda: self.launch_module("Intake", "Local")).grid(row=0, column=1, padx=20, pady=10)

        # Row 1: Sales / POS
        ctk.CTkButton(btn_frame, text="Sell Items / POS", height=60, width=540, fg_color="#2e7d32", hover_color="#1b5e20", command=lambda: self.launch_module("Sales")).grid(row=1, column=0, columnspan=2, pady=10)

        # Row 2: Order Manager (PHASE 3)
        ctk.CTkButton(btn_frame, text="Order Manager (Pending/Shipped)", height=60, width=540, fg_color="#c27b1f", hover_color="#a86815", command=lambda: self.launch_module("Manager")).grid(row=2, column=0, columnspan=2, pady=10)

        # Row 3: Inventory View
        ctk.CTkButton(btn_frame, text="Search & Inventory View", height=60, width=540, fg_color="#1f538d", command=self.show_inventory_search).grid(row=3, column=0, columnspan=2, pady=10)

    # --- ROUTING SYSTEM ---
    def launch_module(self, module_name, source_type=None):
        self.clear_screen()
        if module_name == "Intake":
            view = IntakeModule(self.container, self, source_type)
        elif module_name == "Sales":
            view = SalesModule(self.container, self)
        elif module_name == "Manager":
            view = OrderManagerModule(self.container, self) # <--- NEW ROUTE
        
        view.pack(fill="both", expand=True)

    # --- GLOBAL ERROR HANDLER (UX IMPROVED) ---
    def show_error_popup(self, msg):
        err = ctk.CTkToplevel(self)
        err.title("System Alert")
        err.geometry("500x250") 
        err.attributes("-topmost", True)
        
        textbox = ctk.CTkTextbox(err, font=("Arial", 16), wrap="word")
        textbox.pack(pady=20, padx=20, fill="both", expand=True)
        textbox.insert("0.0", msg)
        textbox.configure(state="disabled") 
        
        # Added Keyboard Binding for 'Enter' key
        btn = ctk.CTkButton(err, text="OK (Press Enter)", command=err.destroy)
        btn.pack(pady=(0, 20))
        err.bind('<Return>', lambda e: err.destroy())
        btn.focus() # Focuses the button so Enter works immediately

    # --- INVENTORY SEARCH ---
    def show_inventory_search(self):
        self.clear_screen()
        nav_bar = ctk.CTkFrame(self.container, height=60, fg_color="#1a1a1a")
        nav_bar.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(nav_bar, text="← Back to Menu", width=120, fg_color="#444", command=self.show_main_menu).pack(side="left", padx=10)

        search_frame = ctk.CTkFrame(self.container, fg_color="transparent")
        search_frame.pack(fill="x", padx=40, pady=10)

        ctk.CTkLabel(search_frame, text="Search Name or QR:", font=("Arial", 14, "bold")).grid(row=0, column=0, padx=10)
        self.search_entry = ctk.CTkEntry(search_frame, width=600, height=40, placeholder_text="Search (Case Insensitive)...")
        self.search_entry.grid(row=0, column=1, padx=10)
        self.search_entry.bind('<Return>', lambda e: self.perform_combined_search())

        ctk.CTkButton(search_frame, text="SEARCH", width=150, height=40, font=("Arial", 13, "bold"), command=self.perform_combined_search).grid(row=0, column=2, padx=10)

        self.results_panel = ctk.CTkScrollableFrame(self.container, width=1200, height=600, fg_color="#242424")
        self.results_panel.pack(pady=10, padx=40, fill="both", expand=True)

    def perform_combined_search(self):
        query = self.search_entry.get().strip().lower()
        for widget in self.results_panel.winfo_children(): widget.destroy()
        if not query: return
        doc = db.collection("products").document(query).get()
        if doc.exists:
            self.display_item_stock(query, doc.to_dict())
            return
        docs = (db.collection("products")
                .where(filter=FieldFilter("name_lower", ">=", query))
                .where(filter=FieldFilter("name_lower", "<=", query + "\uf8ff"))
                .limit(15).get())
        if not docs:
            ctk.CTkLabel(self.results_panel, text="No matches found.", text_color="#bbbbbb", font=("Arial", 16)).pack(pady=40)
            return
        for d in docs:
            p_data = d.to_dict()
            btn = ctk.CTkButton(self.results_panel, text=f"{p_data.get('name')} | {p_data.get('shade')} ({p_data.get('brand')})", anchor="w", height=45, fg_color="#333", command=lambda bar=d.id, data=p_data: self.display_item_stock(bar, data))
            btn.pack(fill="x", pady=3, padx=20)

    def display_item_stock(self, barcode, prod_data):
        for widget in self.results_panel.winfo_children(): widget.destroy()
        header_frame = ctk.CTkFrame(self.results_panel, fg_color="#2b2b2b", corner_radius=10)
        header_frame.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(header_frame, text=prod_data.get('name'), font=("Arial", 22, "bold")).pack(pady=(10,2), padx=20, anchor="w")
        ctk.CTkLabel(header_frame, text=f"Shade: {prod_data.get('shade')} | Brand: {prod_data.get('brand')}", text_color="#3a7ebf").pack(padx=20, anchor="w")
        ctk.CTkLabel(header_frame, text=f"Barcode: {barcode} | Weight: {prod_data.get('weight_g', '0')}g", text_color="gray").pack(pady=(5,10), padx=20, anchor="w")
        
        all_batches_docs = db.collection("batches").where(filter=FieldFilter("barcode", "==", barcode)).get()
        active_batches = [b.to_dict() for b in all_batches_docs if int(b.to_dict().get('qty_remaining', 0)) > 0]
        active_batches.sort(key=lambda x: x.get('timestamp') if x.get('timestamp') else datetime.min)
        
        if not active_batches:
            ctk.CTkLabel(self.results_panel, text="OUT OF STOCK", font=("Arial", 26, "bold"), text_color="#ff4444").pack(pady=40)
        else:
            for b_data in active_batches:
                ts = b_data.get('timestamp')
                ds = ts.strftime("%d/%m/%Y") if ts else "N/A"
                card = ctk.CTkFrame(self.results_panel, fg_color="#333333", border_width=1, border_color="#444")
                card.pack(fill="x", pady=5, padx=10)
                ctk.CTkLabel(card, text=f"Order: {b_data.get('order_id')}\nReceived: {ds}", justify="left").pack(side="left", padx=20, pady=15)
                ctk.CTkLabel(card, text=f"QTY: {b_data['qty_remaining']} pcs\nCOST: {b_data['landed_cost_egp']:.2f} EGP", justify="right", font=("Arial", 14, "bold"), text_color="#3a7ebf").pack(side="right", padx=20, pady=15)

if __name__ == "__main__":
    app = MainApp()
    app.mainloop()