import customtkinter as ctk
from firebase_admin import firestore
from datetime import datetime
from firebase_config import db

class IntakeModule(ctk.CTkFrame):
    def __init__(self, parent, controller, source_type):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.source_type = source_type
        
        self.is_editing = None 
        self.current_order_items = [] 
        self.order_meta = {} 

        self.show_order_setup()

    def clear_view(self):
        for widget in self.winfo_children():
            widget.destroy()

    def show_order_setup(self):
        self.clear_view()
        
        nav_bar = ctk.CTkFrame(self, height=50, fg_color="transparent")
        nav_bar.pack(fill="x", padx=20, pady=10)
        ctk.CTkButton(nav_bar, text="← Back to Menu", width=120, fg_color="#444", command=self.controller.show_main_menu).pack(side="left")
        
        form_frame = ctk.CTkScrollableFrame(self, width=850, height=500)
        form_frame.pack(pady=10, padx=20, fill="both", expand=True)
        
        self.setup_header_fields(form_frame, self.source_type)
        
        ctk.CTkButton(form_frame, text="Clear All Fields", fg_color="#555", command=self.clear_all_header_fields).pack(pady=20)
        
        bottom_bar = ctk.CTkFrame(self, height=80, fg_color="transparent")
        bottom_bar.pack(fill="x", pady=20)
        ctk.CTkButton(bottom_bar, text="PROCEED TO SCANNING →", font=("Arial", 18, "bold"), height=50, width=400, fg_color="green", command=self.capture_and_proceed).pack(expand=True)

    def setup_header_fields(self, parent, source_type):
        self.header_entries = {}
        if source_type == "Global":
            fields = [("Supplier Name *", "e.g., Amazon DE"), ("Courier Name *", "e.g., Nashwa"), ("Currency *", "EUR/USD/TRY"),
                      ("FX Rate 1 (Item) *", "Item Rate"), ("FX Rate 2 (Weight) *", "Weight Rate"),
                      ("Bank Comm % *", "0 if none"), ("Weight/KG (Foreign) *", "0 if none"),
                      ("Fixed: Global Ship (Foreign) *", "0 if none"), ("Fixed: Local Ship (EGP) *", "0 if none"),
                      ("Fixed: Wrapping (EGP) *", "0 if none"), ("Order Overhead (EGP) *", "0 if none"), ("Order Discount (EGP) *", "0 if none"),
                      ("Total Items Count *", "Total pieces")]
        else:
            fields = [("Supplier Name *", "Local Supplier Name"), ("Fixed: Local Ship (EGP) *", "0 if none"), 
                      ("Order Overhead (EGP) *", "0 if none"), ("Order Discount (EGP) *", "0 if none"),
                      ("Total Items Count *", "Total pieces")]
        
        for label, ph in fields:
            row = ctk.CTkFrame(parent, fg_color="transparent"); row.pack(fill="x", pady=5, padx=30)
            ctk.CTkLabel(row, text=label, width=250, anchor="w").pack(side="left")
            entry = ctk.CTkEntry(row, width=350, placeholder_text=ph)
            if label in self.order_meta: entry.insert(0, self.order_meta[label])
            entry.pack(side="right"); self.header_entries[label] = entry

    def clear_all_header_fields(self):
        for entry in self.header_entries.values(): entry.delete(0, 'end')

    def capture_and_proceed(self):
        try:
            temp = {k: v.get().strip() for k, v in self.header_entries.items()}
            for k,v in temp.items(): 
                if not v: raise ValueError(f"{k} is required")
            int(temp['Total Items Count *']); self.order_meta = temp; self.show_product_entry()
        except Exception as e: self.controller.show_error_popup(str(e))

    def show_product_entry(self):
        self.clear_view()
        self.grid_columnconfigure(0, weight=65); self.grid_columnconfigure(1, weight=35)
        
        left_panel = ctk.CTkFrame(self, fg_color="transparent"); left_panel.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        nav_bar = ctk.CTkFrame(left_panel, height=50, fg_color="transparent"); nav_bar.pack(fill="x")
        ctk.CTkButton(nav_bar, text="← General Info", width=120, command=self.show_order_setup).pack(side="left")
        
        # REMOVED the buggy trace_add("write", ...) from here
        self.scan_var = ctk.StringVar()
        
        ctk.CTkLabel(left_panel, text="SCAN QR / BARCODE", font=("Arial", 16, "bold")).pack(pady=(15,0))
        self.barcode_entry = ctk.CTkEntry(left_panel, textvariable=self.scan_var, width=500, height=50, font=("Arial", 22))
        self.barcode_entry.pack(pady=10); self.barcode_entry.focus()
        
        # FIXED: Only search the database when the Enter key is pressed
        self.barcode_entry.bind('<Return>', self.live_search)

        self.status_note = ctk.CTkLabel(left_panel, text="Waiting for scan...", font=("Arial", 14)); self.status_note.pack()
        
        self.form_details_frame = ctk.CTkFrame(left_panel); self.form_details_frame.pack(pady=10, fill="both", expand=True)
        self.setup_product_fields()
        
        btn_f = ctk.CTkFrame(left_panel, fg_color="transparent"); btn_f.pack(pady=15)
        self.save_btn = ctk.CTkButton(btn_f, text="ADD TO ORDER DRAFT", height=50, width=250, fg_color="#1f538d", command=self.save_item_to_draft)
        self.save_btn.grid(row=0, column=0, padx=10)
        ctk.CTkButton(btn_f, text="Clear Form", height=50, width=150, fg_color="#555", command=self.clear_product_fields).grid(row=0, column=1, padx=10)
        
        right_panel = ctk.CTkFrame(self); right_panel.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self.counter_label = ctk.CTkLabel(right_panel, text="Items: 0 / 0", font=("Arial", 16, "bold")); self.counter_label.pack(pady=10)
        self.total_cost_label = ctk.CTkLabel(right_panel, text="Total Cost: 0.00 EGP", font=("Arial", 16, "bold"), text_color="#4CAF50"); self.total_cost_label.pack()
        self.summary_scroll = ctk.CTkScrollableFrame(right_panel, fg_color="#2b2b2b"); self.summary_scroll.pack(fill="both", expand=True, pady=10)
        self.finish_btn = ctk.CTkButton(right_panel, text="FINISH ORDER & COMMIT", height=60, fg_color="green", state="disabled", command=self.commit_order_to_firebase)
        self.finish_btn.pack(pady=20, padx=20)
        self.update_summary_ui()

    def setup_product_fields(self):
        self.prod_entries = {}
        # FIXED: Changed "Selling Price (Optional)" to "Selling Price *"
        fields = ["Name *", "Shade *", "Brand *", "Quantity *", "Weight (g) *", "Selling Price *"]
        fields.append(f"Cost ({self.order_meta['Currency *']}) *" if self.source_type == "Global" else "Cost (EGP) *")
        for f in fields:
            row = ctk.CTkFrame(self.form_details_frame, fg_color="transparent"); row.pack(fill="x", padx=40, pady=4)
            ctk.CTkLabel(row, text=f, width=150, anchor="w").pack(side="left")
            ent = ctk.CTkEntry(row, width=350); ent.pack(side="right"); self.prod_entries[f] = ent

    def live_search(self, *args):
        barcode = self.scan_var.get().strip()
        # FIXED: Only checks the database if the box actually has characters after hitting enter
        if len(barcode) > 0 and not self.is_editing:
            doc = db.collection("products").document(barcode).get()
            if doc.exists:
                self.autofill_master_data(doc.to_dict())
                self.status_note.configure(text="✔ Registered Product", text_color="green")
            else: self.status_note.configure(text="✚ New Product Detected", text_color="#ffcc00")

    def save_item_to_draft(self):
        barcode = self.scan_var.get().strip()
        if not barcode: return
        try:
            data = {}
            for f, e in self.prod_entries.items():
                val = e.get().strip()
                if "*" in f and not val and f != "Weight (g) *": raise ValueError(f"{f} is required")
                data[f] = val
            data['Barcode'] = barcode
            if self.is_editing is not None: self.current_order_items[self.is_editing] = data
            else: self.current_order_items.append(data)
            self.is_editing = None; self.save_btn.configure(text="ADD TO ORDER DRAFT", fg_color="#1f538d")
            self.clear_product_fields(); self.update_summary_ui()
        except Exception as e: self.status_note.configure(text=f"⚠️ {str(e)}", text_color="red")

    def update_summary_ui(self):
        for widget in self.summary_scroll.winfo_children(): widget.destroy()
        aq, tc = 0, 0.0
        ex = int(self.order_meta['Total Items Count *'])
        for i, item in enumerate(self.current_order_items):
            q = int(item['Quantity *'] or 0); aq += q
            lc = self.calculate_final_landed_cost(item); tc += (lc * q)
            f = ctk.CTkFrame(self.summary_scroll, fg_color="#3a3a3a"); f.pack(fill="x", pady=2, padx=2)
            ctk.CTkLabel(f, text=f"{q} | {item['Name *']} | {item['Shade *']}\nUnit: {lc:.2f} EGP", font=("Arial", 11), justify="left").pack(side="left", padx=5)
            ctk.CTkButton(f, text="✎", width=30, command=lambda idx=i: self.load_for_edit(idx)).pack(side="right", padx=2)
            ctk.CTkButton(f, text="✕", width=30, fg_color="#a32e2e", command=lambda idx=i: self.delete_item(idx)).pack(side="right", padx=2)
        self.counter_label.configure(text=f"Items: {aq} / {ex}"); self.total_cost_label.configure(text=f"Total Cost: {tc:,.2f} EGP")
        self.finish_btn.configure(state="normal" if aq == ex else "disabled")

    def load_for_edit(self, index):
        self.is_editing = index; item = self.current_order_items[index]
        self.save_btn.configure(text="UPDATE ITEM", fg_color="orange"); self.scan_var.set(item['Barcode'])
        for f, entry in self.prod_entries.items():
            entry.delete(0, 'end'); entry.insert(0, item.get(f, ''))

    def delete_item(self, index): self.current_order_items.pop(index); self.update_summary_ui()

    def calculate_final_landed_cost(self, item):
        m = self.order_meta
        try:
            tn = int(m['Total Items Count *'])
            overhead = float(m.get('Order Overhead (EGP) *', 0))
            discount = float(m.get('Order Discount (EGP) *', 0))
            if self.source_type == "Global":
                f1, f2, cm, sk = float(m['FX Rate 1 (Item) *']), float(m['FX Rate 2 (Weight) *']), 1+(float(m['Bank Comm % *'])/100), float(m['Weight/KG (Foreign) *'])
                fix = ( (float(m['Fixed: Global Ship (Foreign) *'])*f1) + float(m['Fixed: Local Ship (EGP) *']) + float(m['Fixed: Wrapping (EGP) *']) + overhead - discount ) / tn
                base = float(item[f"Cost ({m['Currency *']}) *"])*f1*cm
                wgt = (float(item.get("Weight (g) *") or 0)/1000)*sk*f2
                return round(base + wgt + fix, 2)
            else:
                fix = (float(m['Fixed: Local Ship (EGP) *']) + overhead - discount) / tn
                return round(float(item["Cost (EGP) *"]) + fix, 2)
        except: return 0.0

    def commit_order_to_firebase(self):
        self.finish_btn.configure(state="disabled", text="UPLOADING...")
        try:
            ds = datetime.now().strftime("%d_%m_%Y")
            sn, cn = self.order_meta['Supplier Name *'].replace(" ",""), self.order_meta.get('Courier Name *', 'Local').replace(" ","")
            oid = f"{ds}_{sn}_{cn}"
            db.collection("orders_history").document(oid).set({"supplier": sn, "courier": cn, "timestamp": firestore.SERVER_TIMESTAMP, "meta": self.order_meta, "type": self.source_type})
            
            for item in self.current_order_items:
                bar = item['Barcode']
                lc = self.calculate_final_landed_cost(item)
                
                # FIXED: Selling price correctly cast to float and uploaded
                update_data = {
                    "name": item['Name *'], 
                    "name_lower": item['Name *'].lower(), 
                    "shade": item['Shade *'], 
                    "brand": item['Brand *'], 
                    "selling_price": float(item.get('Selling Price *', 0)),
                    "last_updated": firestore.SERVER_TIMESTAMP
                }
                new_weight = float(item.get("Weight (g) *") or 0)
                if new_weight > 0: update_data["weight_g"] = new_weight
                
                db.collection("products").document(bar).set(update_data, merge=True)
                db.collection("batches").add({"barcode": bar, "order_id": oid, "landed_cost_egp": lc, "qty_initial": int(item['Quantity *']), "qty_remaining": int(item['Quantity *']), "timestamp": firestore.SERVER_TIMESTAMP})
            
            self.controller.show_main_menu()
            if hasattr(self.controller, 'show_error_popup'):
                self.controller.show_error_popup("Intake Order Committed Successfully!")
        except Exception as e: 
            self.finish_btn.configure(state="normal", text="RETRY COMMIT")
            print(e)

    def autofill_master_data(self, data):
        # FIXED: Properly autofills the selling price if the product already exists
        mapping = {"Name *": "name", "Shade *": "shade", "Brand *": "brand", "Weight (g) *": "weight_g", "Selling Price *": "selling_price"}
        for ui, db_key in mapping.items():
            if ui in self.prod_entries:
                self.prod_entries[ui].delete(0, 'end')
                self.prod_entries[ui].insert(0, str(data.get(db_key, '')))

    def clear_product_fields(self):
        self.scan_var.set("")
        for e in self.prod_entries.values(): e.delete(0, 'end')
        self.barcode_entry.focus()