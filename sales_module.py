import customtkinter as ctk
from firebase_config import db
from google.cloud.firestore_v1.base_query import FieldFilter
from firebase_admin import firestore
from datetime import datetime

class SalesModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.pos_cart = {} 
        self.setup_ui()

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=55)
        self.grid_columnconfigure(1, weight=45)

        left_p = ctk.CTkFrame(self, fg_color="transparent")
        left_p.grid(row=0, column=0, sticky="nsew", padx=20, pady=20)
        
        ctk.CTkButton(left_p, text="← Back to Menu", width=120, fg_color="#444", command=self.controller.show_main_menu).pack(anchor="w")
        ctk.CTkLabel(left_p, text="POS CHECKOUT", font=("Arial", 24, "bold")).pack(pady=10)

        search_f = ctk.CTkFrame(left_p, fg_color="transparent")
        search_f.pack(fill="x", pady=10)
        self.pos_scan_var = ctk.StringVar()
        self.pos_scan_entry = ctk.CTkEntry(search_f, textvariable=self.pos_scan_var, width=350, height=45, placeholder_text="Scan Barcode or Type Name...")
        self.pos_scan_entry.pack(side="left", padx=5)
        self.pos_scan_entry.bind('<Return>', lambda e: self.search_and_add())
        ctk.CTkButton(search_f, text="SEARCH", width=100, height=45, command=self.search_and_add).pack(side="left", padx=5)

        header_f = ctk.CTkFrame(left_p, fg_color="#222")
        header_f.pack(fill="x", pady=(10, 0))
        ctk.CTkLabel(header_f, text="Product Info", width=250, anchor="w").pack(side="left", padx=10)
        ctk.CTkLabel(header_f, text="Price", width=80).pack(side="right", padx=30)
        ctk.CTkLabel(header_f, text="Qty", width=50).pack(side="right", padx=10)

        self.pos_cart_scroll = ctk.CTkScrollableFrame(left_p, fg_color="#1a1a1a")
        self.pos_cart_scroll.pack(fill="both", expand=True, pady=5)

        right_p = ctk.CTkFrame(self, fg_color="#2b2b2b")
        right_p.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        
        scroll_right = ctk.CTkScrollableFrame(right_p, fg_color="transparent")
        scroll_right.pack(fill="both", expand=True)

        ctk.CTkLabel(scroll_right, text="Order Details", font=("Arial", 18, "bold")).pack(pady=10)

        self.entries = {}
        fields = [
            ("Sales Channel *", ["Messenger", "Instagram", "Shopify", "Noon"]), 
            ("Initial Status *", ["ACTIVE", "SHIPPED"]), # <--- STREAMLINED STATUSES
            ("Order ID (External) *", "Obligatory (e.g., Shopify#, Messenger)"), 
            ("Shipment Option *", ["Self Shipment", "Sharex", "Noon"]),
            ("Shipment ID", ""),
            ("Customer Name *", "Client's full name"),
            ("Customer Phone *", "Exactly 11 digits"), 
            ("Address *", ""), 
            ("Notes", "Optional notes..."),
            ("Total Sale Price (EGP) *", "Auto-calculated"), 
            ("Deposit Paid (EGP) *", "0")
        ]
        
        for label, data in fields:
            ctk.CTkLabel(scroll_right, text=label).pack(anchor="w", padx=20, pady=(5,0))
            if isinstance(data, list):
                widget = ctk.CTkComboBox(scroll_right, values=data, width=320)
            else:
                widget = ctk.CTkEntry(scroll_right, width=320, placeholder_text=data)
                if label == "Total Sale Price (EGP) *":
                    self.total_entry = widget
            widget.pack(pady=(0, 5), padx=20)
            self.entries[label] = widget

        self.checkout_btn = ctk.CTkButton(scroll_right, text="CREATE ORDER", height=60, width=320, 
                                          fg_color="green", font=("Arial", 16, "bold"), command=self.process_checkout)
        self.checkout_btn.pack(pady=20)

    def search_and_add(self):
        query = self.pos_scan_var.get().strip().lower()
        self.pos_scan_var.set("")
        if not query: return
        doc = db.collection("products").document(query).get()
        if doc.exists:
            self.add_to_dict(query, doc.to_dict())
            return
        docs = db.collection("products").where(filter=FieldFilter("name_lower", ">=", query)).where(filter=FieldFilter("name_lower", "<=", query + "\uf8ff")).limit(10).get()
        if not docs:
            if hasattr(self.controller, 'show_error_popup'): self.controller.show_error_popup("No product found.")
            return
        self.show_suggestion_popup(docs)

    def show_suggestion_popup(self, docs):
        popup = ctk.CTkToplevel(self)
        popup.title("Select Product")
        popup.geometry("500x400")
        popup.attributes("-topmost", True)
        ctk.CTkLabel(popup, text="Multiple matches found. Select one:", font=("Arial", 16, "bold")).pack(pady=10)
        scroll = ctk.CTkScrollableFrame(popup, width=450, height=300)
        scroll.pack(pady=10, padx=10, fill="both", expand=True)

        for d in docs:
            p_data = d.to_dict(); barcode = d.id
            btn = ctk.CTkButton(scroll, text=f"{p_data.get('name')} | {p_data.get('shade')}", anchor="w", fg_color="#333", hover_color="#444",
                                command=lambda b=barcode, pd=p_data, pop=popup: self.select_from_popup(b, pd, pop))
            btn.pack(fill="x", pady=2)

    def select_from_popup(self, barcode, p_data, popup):
        self.add_to_dict(barcode, p_data)
        popup.destroy()

    def add_to_dict(self, barcode, data):
        if barcode in self.pos_cart:
            self.pos_cart[barcode]['qty'] += 1
        else:
            self.pos_cart[barcode] = {"name": data.get('name'), "shade": data.get('shade'), "qty": 1, "selling_price": float(data.get('selling_price', 0.0))}
        self.refresh_cart_ui()
        self.recalculate_total()

    def update_cart_value(self, barcode, key, string_var):
        val = string_var.get()
        try:
            if key == 'qty': self.pos_cart[barcode][key] = int(val) if val else 0
            else: self.pos_cart[barcode][key] = float(val) if val else 0.0
            self.recalculate_total()
        except ValueError: pass

    def recalculate_total(self):
        total = sum(item['qty'] * item['selling_price'] for item in self.pos_cart.values())
        self.total_entry.delete(0, 'end')
        self.total_entry.insert(0, str(round(total, 2)))

    def refresh_cart_ui(self):
        for widget in self.pos_cart_scroll.winfo_children(): widget.destroy()
        for barcode, item in self.pos_cart.items():
            f = ctk.CTkFrame(self.pos_cart_scroll, fg_color="#333")
            f.pack(fill="x", pady=2, padx=5)
            ctk.CTkButton(f, text="✕", width=30, fg_color="#a32e2e", command=lambda b=barcode: self.remove_from_pos(b)).pack(side="left", padx=5, pady=5)
            ctk.CTkLabel(f, text=f"{item['name']} | {item['shade']}", font=("Arial", 12), width=180, anchor="w").pack(side="left", padx=5)
            
            price_var = ctk.StringVar(value=str(item['selling_price']))
            price_ent = ctk.CTkEntry(f, textvariable=price_var, width=60)
            price_ent.pack(side="right", padx=5)
            price_var.trace_add("write", lambda *args, b=barcode, pv=price_var: self.update_cart_value(b, 'selling_price', pv))
            
            qty_var = ctk.StringVar(value=str(item['qty']))
            qty_ent = ctk.CTkEntry(f, textvariable=qty_var, width=40)
            qty_ent.pack(side="right", padx=10)
            qty_var.trace_add("write", lambda *args, b=barcode, qv=qty_var: self.update_cart_value(b, 'qty', qv))

    def remove_from_pos(self, barcode): 
        del self.pos_cart[barcode]; self.refresh_cart_ui(); self.recalculate_total()

    def process_checkout(self):
        if not self.pos_cart:
            if hasattr(self.controller, 'show_error_popup'): self.controller.show_error_popup("Cart is empty!")
            return
        try:
            self.checkout_btn.configure(state="disabled", text="PROCESSING...")
            order_data = {k: v.get().strip() for k, v in self.entries.items()}
            phone = order_data["Customer Phone *"]
            ext_id = order_data["Order ID (External) *"]
            if not phone.isdigit() or len(phone) != 11: raise ValueError("Phone number must be exactly 11 digits!")
            if not order_data["Address *"] or not order_data["Total Sale Price (EGP) *"] or not order_data["Customer Name *"] or not ext_id:
                raise ValueError("Name, Ext ID, Address, and Total Sale Price are required!")

            final_items = []
            for barcode, item in self.pos_cart.items():
                needed_qty = item['qty']
                if needed_qty <= 0: continue

                all_batches_docs = db.collection("batches").where(filter=FieldFilter("barcode", "==", barcode)).get()
                active_batches = [b for b in all_batches_docs if int(b.to_dict().get('qty_remaining', 0)) > 0]
                active_batches.sort(key=lambda x: x.to_dict().get('timestamp') if x.to_dict().get('timestamp') else datetime.min)

                available_qty = sum(b.to_dict().get('qty_remaining', 0) for b in active_batches)
                if available_qty < needed_qty:
                    raise ValueError(f"Only {available_qty} in stock for {item['name']}. You asked for {needed_qty}.")
                
                qty_to_subtract = needed_qty
                for batch in active_batches:
                    b_data = batch.to_dict()
                    b_id = batch.id
                    b_qty = b_data.get('qty_remaining', 0)
                    
                    if b_qty >= qty_to_subtract:
                        db.collection("batches").document(b_id).update({"qty_remaining": firestore.Increment(-qty_to_subtract)})
                        final_items.append({"barcode": barcode, "batch_id": b_id, "name": item['name'], "shade": item['shade'], "qty": qty_to_subtract, "selling_price": item['selling_price'], "landed_cost": b_data['landed_cost_egp']})
                        qty_to_subtract = 0
                        break
                    else:
                        db.collection("batches").document(b_id).update({"qty_remaining": 0})
                        final_items.append({"barcode": barcode, "batch_id": b_id, "name": item['name'], "shade": item['shade'], "qty": b_qty, "selling_price": item['selling_price'], "landed_cost": b_data['landed_cost_egp']})
                        qty_to_subtract -= b_qty
            
            clean_name = "".join(e for e in order_data["Customer Name *"] if e.isalnum())
            total_val = float(order_data["Total Sale Price (EGP) *"])
            date_str = datetime.now().strftime("%y%m%d_%H%M")
            readable_id = f"{ext_id}_{clean_name}_{total_val}_{date_str}"

            db.collection("sales_orders").document(readable_id).set({
                "status": order_data["Initial Status *"], 
                "channel": order_data["Sales Channel *"], 
                "external_id": ext_id,
                "shipment_option": order_data["Shipment Option *"],
                "shipment_id": order_data["Shipment ID"],
                "customer_name": order_data["Customer Name *"],
                "customer_phone": phone, 
                "address": order_data["Address *"],
                "notes": order_data["Notes"],
                "total_sale_value": total_val, 
                "deposit_paid": float(order_data["Deposit Paid (EGP) *"] or 0), 
                "payout_received": 0.0,
                "items": final_items, 
                "created_at": firestore.SERVER_TIMESTAMP,
                "completed_at": None
            })
            self.controller.show_main_menu()
        except Exception as e: 
            self.checkout_btn.configure(state="normal", text="CREATE ORDER")
            if hasattr(self.controller, 'show_error_popup'): self.controller.show_error_popup(str(e))