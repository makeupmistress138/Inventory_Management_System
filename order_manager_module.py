import customtkinter as ctk
from firebase_config import db
from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime

class OrderManagerModule(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.selected_order_id = None
        self.selected_order_data = None
        self.edit_cart = {} 
        
        self.setup_ui()
        self.load_orders()

    def setup_ui(self):
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=35)
        self.grid_columnconfigure(1, weight=65)

        # --- LEFT PANEL: LIST & FILTERS ---
        left_p = ctk.CTkFrame(self, fg_color="#1a1a1a")
        left_p.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        nav_bar = ctk.CTkFrame(left_p, fg_color="transparent")
        nav_bar.pack(fill="x", pady=10, padx=10)
        ctk.CTkButton(nav_bar, text="← Back", width=60, fg_color="#444", command=self.controller.show_main_menu).pack(side="left")
        ctk.CTkButton(nav_bar, text="↻ Refresh", width=60, fg_color="#1f538d", command=self.load_orders).pack(side="right")

        filter_f = ctk.CTkFrame(left_p, fg_color="transparent")
        filter_f.pack(fill="x", padx=10, pady=5)
        
        self.filter_var = ctk.StringVar(value="ACTIVE")
        status_opts = ["ACTIVE", "PENDING", "CONFIRMED", "SHIPPED", "COMPLETED", "RETURNED", "CANCELLED", "ALL"]
        combo = ctk.CTkComboBox(filter_f, values=status_opts, variable=self.filter_var, command=lambda e: self.load_orders())
        combo.pack(fill="x", pady=2)

        self.search_var = ctk.StringVar()
        s_ent = ctk.CTkEntry(filter_f, textvariable=self.search_var, placeholder_text="Search ID, Name, Phone...")
        s_ent.pack(fill="x", pady=2)
        s_ent.bind('<Return>', lambda e: self.load_orders())

        self.order_list_scroll = ctk.CTkScrollableFrame(left_p, fg_color="transparent")
        self.order_list_scroll.pack(fill="both", expand=True, padx=5, pady=5)

        # --- RIGHT PANEL: DETAILS ---
        self.right_p = ctk.CTkFrame(self, fg_color="#2b2b2b")
        self.right_p.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.details_container = ctk.CTkFrame(self.right_p, fg_color="transparent")
        self.details_container.pack(fill="both", expand=True, padx=20, pady=10)

    def load_orders(self):
        for w in self.order_list_scroll.winfo_children(): w.destroy()
        
        f_status = self.filter_var.get()
        q_search = self.search_var.get().strip().lower()

        all_orders = db.collection("sales_orders").get()
        valid_orders = []

        for o in all_orders:
            data = o.to_dict()
            status = data.get("status", "")
            if f_status == "ACTIVE" and status in ["COMPLETED", "CANCELLED", "RETURNED"]: continue
            if f_status not in ["ALL", "ACTIVE"] and status != f_status: continue
            
            search_str = f"{o.id} {data.get('customer_name','')} {data.get('customer_phone','')}".lower()
            if q_search and q_search not in search_str: continue
            
            valid_orders.append((o.id, data))
                
        valid_orders.sort(key=lambda x: x[1].get('created_at') if x[1].get('created_at') else datetime.min, reverse=True)

        for o_id, data in valid_orders:
            name = data.get('customer_name', 'Unknown')
            btn_text = f"[{data.get('status')}] {name}\nID: {o_id}"
            btn = ctk.CTkButton(self.order_list_scroll, text=btn_text, anchor="w", fg_color="#333", hover_color="#444",
                                command=lambda oid=o_id, d=data: self.render_order_details(oid, d))
            btn.pack(fill="x", pady=5)

    def render_order_details(self, order_id, data):
        self.selected_order_id = order_id
        self.selected_order_data = data
        current_status = data.get('status', '')
        for w in self.details_container.winfo_children(): w.destroy()

        self.edit_cart = {}
        for item in data.get('items', []):
            bc = item['barcode']
            if bc not in self.edit_cart:
                self.edit_cart[bc] = {"name": item['name'], "shade": item.get('shade', ''), "qty": 0, "selling_price": item.get('selling_price', 0.0)}
            self.edit_cart[bc]['qty'] += item.get('qty', 0)

        # 1. HEADER
        header = ctk.CTkFrame(self.details_container, fg_color="#1a1a1a", corner_radius=10)
        header.pack(fill="x", pady=(0, 10))
        
        ctk.CTkLabel(header, text=f"Order: {order_id}", text_color="gray", font=("Arial", 12)).pack(anchor="w", padx=10, pady=(5,0))
        ctk.CTkLabel(header, text=data.get('customer_name', 'No Name'), font=("Arial", 20, "bold")).pack(anchor="w", padx=10)
        info_text = f"Phone: {data.get('customer_phone')}  |  Address: {data.get('address')}\n" \
                    f"Channel: {data.get('channel')}  |  Shipment: {data.get('shipment_option')} (ID: {data.get('shipment_id', 'N/A')})\n" \
                    f"Total: {data.get('total_sale_value')} EGP  |  Deposit: {data.get('deposit_paid')} EGP\n" \
                    f"Notes: {data.get('notes', 'None')}"
        ctk.CTkLabel(header, text=info_text, justify="left", font=("Arial", 14)).pack(anchor="w", padx=10, pady=10)

        is_locked = current_status in ["COMPLETED", "CANCELLED", "RETURNED"]

        # 2. ITEMS SCROLL
        ctk.CTkLabel(self.details_container, text="Draft Edit Cart (Click Update to Save):" if not is_locked else "Final Order Items:", font=("Arial", 16, "bold")).pack(anchor="w")
        self.items_scroll = ctk.CTkScrollableFrame(self.details_container, fg_color="transparent")
        self.items_scroll.pack(fill="both", expand=True, pady=5)
        self.draw_edit_cart(is_locked)

        if not is_locked:
            add_f = ctk.CTkFrame(self.details_container, fg_color="#222")
            add_f.pack(fill="x", pady=5)
            self.add_scan_var = ctk.StringVar()
            add_ent = ctk.CTkEntry(add_f, textvariable=self.add_scan_var, placeholder_text="Scan Barcode or Type Name to Add...", width=300)
            add_ent.pack(side="left", padx=10, pady=10)
            add_ent.bind('<Return>', lambda e: self.search_and_add_item())
            ctk.CTkButton(add_f, text="Search & Add", width=100, fg_color="#1f538d", command=self.search_and_add_item).pack(side="left", padx=5)

            ctk.CTkButton(self.details_container, text="UPDATE ORDER ITEMS (Save Changes)", fg_color="#2e7d32", height=40, font=("Arial", 14, "bold"),
                          command=self.update_order_items).pack(fill="x", pady=10)

        # 3. ACTION BUTTONS (STATE MACHINE)
        actions_f = ctk.CTkFrame(self.details_container, fg_color="transparent")
        actions_f.pack(fill="x", pady=10)

        stat_f = ctk.CTkFrame(actions_f, fg_color="transparent")
        stat_f.pack(fill="x", pady=5)
        ctk.CTkLabel(stat_f, text="Current Status:").pack(side="left", padx=5)
        
        # ONE-WAY STATE LOGIC
        allowed_states = [current_status]
        if current_status == "PENDING": allowed_states = ["PENDING", "CONFIRMED", "SHIPPED"]
        elif current_status == "CONFIRMED": allowed_states = ["CONFIRMED", "SHIPPED"]
        elif current_status == "SHIPPED": allowed_states = ["SHIPPED"]

        self.status_var = ctk.StringVar(value=current_status)
        combo = ctk.CTkComboBox(stat_f, values=allowed_states, variable=self.status_var, width=150)
        combo.pack(side="left", padx=5)
        btn_stat = ctk.CTkButton(stat_f, text="Save Status Only", width=120, command=self.update_status)
        btn_stat.pack(side="left", padx=5)

        bot_f = ctk.CTkFrame(actions_f, fg_color="transparent")
        bot_f.pack(fill="x", pady=5)
        
        btn_cancel = ctk.CTkButton(bot_f, text="CANCEL ORDER", fg_color="#a32e2e", command=self.cancel_order)
        btn_cancel.pack(side="left", expand=True, padx=2)
        
        btn_return = ctk.CTkButton(bot_f, text="RETURN / LOSS", fg_color="#c27b1f", command=lambda: self.process_return(is_rma=False))
        btn_return.pack(side="left", expand=True, padx=2)
        
        btn_complete = ctk.CTkButton(bot_f, text="MARK COMPLETED", fg_color="green", command=self.trigger_completion)
        btn_complete.pack(side="right", expand=True, padx=2)

        btn_rma = ctk.CTkButton(bot_f, text="START RMA (Refund)", fg_color="#8e24aa", command=lambda: self.process_return(is_rma=True))

        # Enforce Guardrails
        if is_locked:
            combo.configure(state="disabled")
            btn_stat.configure(state="disabled")
            btn_cancel.pack_forget()
            btn_return.pack_forget()
            btn_complete.pack_forget()
            if current_status == "COMPLETED":
                btn_rma.pack(side="left", expand=True, padx=2)
        elif current_status == "PENDING":
            btn_return.configure(state="disabled")
            btn_complete.configure(state="disabled")
        else:
            btn_cancel.configure(state="disabled")

    def draw_edit_cart(self, is_locked=False):
        for w in self.items_scroll.winfo_children(): w.destroy()
        for barcode, item in self.edit_cart.items():
            f = ctk.CTkFrame(self.items_scroll, fg_color="#333")
            f.pack(fill="x", pady=2)
            if not is_locked: ctk.CTkButton(f, text="-", width=30, command=lambda b=barcode: self.change_qty(b, -1)).pack(side="left", padx=5, pady=5)
            ctk.CTkLabel(f, text=str(item['qty']), width=30, font=("Arial", 14, "bold")).pack(side="left", padx=5)
            if not is_locked: ctk.CTkButton(f, text="+", width=30, command=lambda b=barcode: self.change_qty(b, 1)).pack(side="left", padx=5)
            ctk.CTkLabel(f, text=f"{item['name']} | {item['shade']} @ {item['selling_price']} EGP", justify="left").pack(side="left", padx=15)
            if not is_locked: ctk.CTkButton(f, text="✕", width=30, fg_color="#a32e2e", command=lambda b=barcode: self.remove_from_edit(b)).pack(side="right", padx=10)

    def change_qty(self, barcode, delta):
        new_qty = self.edit_cart[barcode]['qty'] + delta
        if new_qty < 0: return
        self.edit_cart[barcode]['qty'] = new_qty
        self.draw_edit_cart(False)

    def remove_from_edit(self, barcode):
        del self.edit_cart[barcode]; self.draw_edit_cart(False)

    def search_and_add_item(self):
        query = self.add_scan_var.get().strip().lower()
        self.add_scan_var.set("")
        if not query: return
        doc = db.collection("products").document(query).get()
        if doc.exists:
            self.add_to_edit_dict(query, doc.to_dict())
            return
        docs = db.collection("products").where(filter=FieldFilter("name_lower", ">=", query)).where(filter=FieldFilter("name_lower", "<=", query + "\uf8ff")).limit(10).get()
        if not docs:
            self.controller.show_error_popup("No product found.")
            return
        self.show_suggestion_popup(docs)

    def show_suggestion_popup(self, docs):
        popup = ctk.CTkToplevel(self)
        popup.title("Select Product to Add")
        popup.geometry("500x400")
        popup.attributes("-topmost", True)
        scroll = ctk.CTkScrollableFrame(popup, width=450, height=300)
        scroll.pack(pady=10, padx=10, fill="both", expand=True)
        for d in docs:
            p_data = d.to_dict(); barcode = d.id
            ctk.CTkButton(scroll, text=f"{p_data.get('name')} | {p_data.get('shade')}", anchor="w", fg_color="#333",
                          command=lambda b=barcode, pd=p_data, pop=popup: self.select_from_popup(b, pd, pop)).pack(fill="x", pady=2)

    def select_from_popup(self, barcode, p_data, popup):
        self.add_to_edit_dict(barcode, p_data); popup.destroy()

    def add_to_edit_dict(self, barcode, data):
        if barcode in self.edit_cart: self.edit_cart[barcode]['qty'] += 1
        else: self.edit_cart[barcode] = {"name": data.get('name'), "shade": data.get('shade'), "qty": 1, "selling_price": float(data.get('selling_price', 0.0))}
        self.draw_edit_cart(False)

    def update_order_items(self):
        try:
            old_items = self.selected_order_data.get('items', [])
            for barcode, cart_item in self.edit_cart.items():
                needed = cart_item['qty']
                held = sum(int(i.get('qty', 0)) for i in old_items if i['barcode'] == barcode)
                if needed > held:
                    extra_needed = needed - held
                    all_batches = db.collection("batches").where(filter=FieldFilter("barcode", "==", barcode)).get()
                    avail = sum(int(b.to_dict().get('qty_remaining', 0)) for b in all_batches)
                    if avail < extra_needed: raise ValueError(f"Not enough stock for {cart_item['name']}. Need {extra_needed} more.")

            for item in old_items:
                b_id = item.get('batch_id')
                if b_id: db.collection("batches").document(b_id).update({"qty_remaining": firestore.Increment(int(item.get('qty', 0)))})

            final_items = []; new_total = 0.0
            for barcode, cart_item in self.edit_cart.items():
                needed_qty = cart_item['qty']
                if needed_qty <= 0: continue
                all_batches_docs = db.collection("batches").where(filter=FieldFilter("barcode", "==", barcode)).get()
                active_batches = [b for b in all_batches_docs if int(b.to_dict().get('qty_remaining', 0)) > 0]
                active_batches.sort(key=lambda x: x.to_dict().get('timestamp') if x.to_dict().get('timestamp') else datetime.min)
                
                qty_to_subtract = needed_qty
                for batch in active_batches:
                    b_data = batch.to_dict(); b_id = batch.id; b_qty = b_data.get('qty_remaining', 0)
                    if b_qty >= qty_to_subtract:
                        db.collection("batches").document(b_id).update({"qty_remaining": firestore.Increment(-qty_to_subtract)})
                        final_items.append({"barcode": barcode, "batch_id": b_id, "name": cart_item['name'], "shade": cart_item['shade'], "qty": qty_to_subtract, "selling_price": cart_item['selling_price'], "landed_cost": b_data['landed_cost_egp']})
                        qty_to_subtract = 0; break
                    else:
                        db.collection("batches").document(b_id).update({"qty_remaining": 0})
                        final_items.append({"barcode": barcode, "batch_id": b_id, "name": cart_item['name'], "shade": cart_item['shade'], "qty": b_qty, "selling_price": cart_item['selling_price'], "landed_cost": b_data['landed_cost_egp']})
                        qty_to_subtract -= b_qty
                new_total += (needed_qty * cart_item['selling_price'])

            db.collection("sales_orders").document(self.selected_order_id).update({"items": final_items, "total_sale_value": new_total})
            self.controller.show_error_popup("Order Items Updated successfully.")
            self.refresh_current_order()
        except Exception as e: self.controller.show_error_popup(f"Failed to update: {str(e)}")

    def refresh_current_order(self):
        current_id = self.selected_order_id
        self.load_orders()
        doc = db.collection("sales_orders").document(current_id).get()
        if doc.exists: self.render_order_details(doc.id, doc.to_dict())

    def update_status(self):
        db.collection("sales_orders").document(self.selected_order_id).update({"status": self.status_var.get()})
        self.controller.show_error_popup("Status Updated.")
        self.refresh_current_order()

    def cancel_order(self):
        items = self.selected_order_data.get('items', [])
        for item in items:
            b_id = item.get('batch_id')
            if b_id: db.collection("batches").document(b_id).update({"qty_remaining": firestore.Increment(int(item.get('qty', 0)))})
        db.collection("sales_orders").document(self.selected_order_id).update({"status": "CANCELLED"})
        self.controller.show_error_popup("Order Cancelled. Stock restored.")
        self.refresh_current_order()

    def process_return(self, is_rma=False):
        data = self.selected_order_data
        items = data.get('items', [])
        
        popup = ctk.CTkToplevel(self)
        popup.title("Post-Completion RMA" if is_rma else "Process Pre-Completion Return")
        popup.geometry("600x500")
        popup.attributes("-topmost", True)
        
        lbl_txt = "Enter Refund Amount to Client (EGP):" if is_rma else "Enter Courier penalty/loss (EGP):"
        ctk.CTkLabel(popup, text=lbl_txt, font=("Arial", 16)).pack(pady=(10, 0))
        amt_var = ctk.StringVar(value="0")
        ctk.CTkEntry(popup, textvariable=amt_var, justify="center").pack(pady=10)

        ctk.CTkLabel(popup, text="Verify Returned Items Condition:", font=("Arial", 14, "bold")).pack(pady=(10, 0))
        item_scroll = ctk.CTkScrollableFrame(popup, fg_color="#1a1a1a")
        item_scroll.pack(fill="both", expand=True, padx=10, pady=5)

        condition_vars = []
        for idx, item in enumerate(items):
            f = ctk.CTkFrame(item_scroll, fg_color="#333")
            f.pack(fill="x", pady=2)
            ctk.CTkLabel(f, text=f"{item['qty']}x {item['name']}").pack(side="left", padx=10, pady=5)
            var = ctk.StringVar(value="Restock")
            ctk.CTkOptionMenu(f, variable=var, values=["Restock", "Damaged (Write-off)"], width=150, fg_color="#1f538d").pack(side="right", padx=10)
            condition_vars.append((item, var))

        def confirm():
            try:
                entered_amt = float(amt_var.get())
                defective_loss = 0.0
                
                for item, var in condition_vars:
                    b_id = item.get('batch_id')
                    qty = int(item.get('qty', 0))
                    condition = var.get()
                    
                    if condition == "Restock":
                        if b_id: db.collection("batches").document(b_id).update({"qty_remaining": firestore.Increment(qty)})
                    else:
                        # Add landed cost to shrinkage bucket
                        defective_loss += float(item.get('landed_cost', 0)) * qty

                # CORE CONTRA-REVENUE ACCOUNTING LOGIC
                update_dict = {
                    "status": "RETURNED", 
                    "returned_at": firestore.SERVER_TIMESTAMP,
                    "defective_loss": defective_loss
                }
                
                if is_rma:
                    # An RMA is a partial/full refund. The revenue reversed is what you refunded.
                    update_dict["sales_return_value"] = entered_amt
                else:
                    # A pre-completion return. The revenue reversed is the entire order value.
                    # The fee you paid the courier is stored in delivery_loss.
                    update_dict["sales_return_value"] = data.get('total_sale_value', 0)
                    update_dict["delivery_loss"] = entered_amt

                db.collection("sales_orders").document(self.selected_order_id).update(update_dict)
                popup.destroy()
                self.controller.show_error_popup("Return Processed. Financial Ledgers updated.")
                self.refresh_current_order()
            except ValueError: pass

        ctk.CTkButton(popup, text="CONFIRM RETURN", fg_color="#c27b1f", command=confirm).pack(pady=10)

    def trigger_completion(self):
        data = self.selected_order_data
        popup = ctk.CTkToplevel(self)
        popup.title("Complete Order")
        popup.geometry("450x250")
        popup.attributes("-topmost", True)
        
        ctk.CTkLabel(popup, text="Enter Final Payout Received (EGP):").pack(pady=10)
        default_payout = max(0, data.get('total_sale_value', 0) - data.get('deposit_paid', 0))
        payout_var = ctk.StringVar(value=str(default_payout))
        ctk.CTkEntry(popup, textvariable=payout_var, justify="center").pack(pady=10)

        def confirm():
            try:
                payout = float(payout_var.get())
                db.collection("sales_orders").document(self.selected_order_id).update({"status": "COMPLETED", "payout_received": payout, "completed_at": firestore.SERVER_TIMESTAMP})
                popup.destroy()
                self.controller.show_error_popup("Completed! Revenue logged.")
                self.refresh_current_order()
            except ValueError: pass
        ctk.CTkButton(popup, text="SAVE & COMPLETE", fg_color="green", command=confirm).pack(pady=10)