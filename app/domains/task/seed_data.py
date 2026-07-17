"""Sample dataset for /tasks/seed-demo-data — recreates the WORKLAB reference
screenshot ("Phan tich Hanh vi Gio hang E-commerce") as a root task split into
2 sub-tasks (20 + 30 = 50 points, matching the original single-task mockup's
"+50 Diem nang luc"), demonstrating parent_task_id nesting and cumulative
scoring end to end.
"""

SEED_COMPANY = {
    "name": "Tiki Corporation",
    "slug": "tiki-corporation",
    "industry": "E-commerce",
    "description": "San thuong mai dien tu hang dau Viet Nam.",
    "website_url": "https://tiki.vn",
    "contact_email": "partner@tiki.vn",
    "is_verified": True,
}

# Root task: no competency_points of its own (has sub-tasks -> points are
# summed from them at read time). No inputs/outputs/criteria of its own either
# — those live on the sub-tasks, which carry the actual deliverables.
SEED_ROOT_TASK = {
    "title": "Phan tich Hanh vi Gio hang E-commerce",
    "difficulty": "MEDIUM",
    "estimated_hours_min": 4,
    "estimated_hours_max": 6,
    "competency_points": None,
    "context": (
        "Doi ngu Product tai Tiki dang nhan thay ti le rot don (drop-off rate) tai buoc "
        "Thanh toan (Checkout) tang 15% trong thang qua. Nhiem vu cua ban la dong vai mot "
        "Data Analyst Junior, phan tich tap du lieu hanh vi nhap chuot va thoi gian dung "
        "tren trang de xac dinh nguyen nhan tiem an va dua ra gia thuyet cai thien."
    ),
    "scope_included": [
        "Phan tich luong hanh vi (User flow) tu man hinh Gio hang den Thanh toan thanh cong.",
        "Tap trung vao phan khuc nguoi dung Mobile App (iOS & Android).",
    ],
    "scope_excluded": [
        "Khong bao gom phan tich du lieu giao dich tai chinh hay cong thanh toan ben thu ba.",
    ],
    "requires_auto_check": True,
    "requires_mentor_approval": True,
    "mentor_approval_sla_hours": 48,
    "data_privacy_notice": (
        "Tap du lieu cung cap thuoc so huu cua doanh nghiep doi tac va da duoc an danh. "
        "Yeu cau khong chia se, sao chep hoac phat tan ra ngoai he thong duoi moi hinh thuc."
    ),
    "inputs": [],
    "outputs": [],
    "criteria": [],
}

SEED_SUB_TASKS = [
    {
        "title": "Lam sach & kham pha du lieu hanh vi",
        "difficulty": "EASY",
        "estimated_hours_min": 1,
        "estimated_hours_max": 2,
        "competency_points": 20,
        "context": "Lam sach tap su kien checkout va loai bo cac event loi/trung lap truoc khi phan tich.",
        "scope_included": ["Loai bo event loi, chuan hoa timestamp, kiem tra tinh toan ven du lieu."],
        "scope_excluded": [],
        "requires_auto_check": True,
        "requires_mentor_approval": False,
        "mentor_approval_sla_hours": None,
        "data_privacy_notice": None,
        "inputs": [
            {"name": "checkout_events_q3.csv", "description": "Tap du lieu 50k+ dong (Da an danh)", "input_type": "DATASET", "is_restricted": True},
            {"name": "Data Dictionary", "description": "Tai lieu mo ta cac truong du lieu", "input_type": "DOCUMENT", "is_restricted": False},
        ],
        "outputs": [
            {"sort_order": 1, "description": "File du lieu da lam sach (CSV) kem ghi chu cac buoc xu ly."},
        ],
        "criteria": [
            {"criterion": "Lam sach va xu ly du lieu dung logic (khong tinh cac event loi).", "weight_percent": 100},
        ],
    },
    {
        "title": "Xac dinh Drop-off Point & Xay Dashboard",
        "difficulty": "MEDIUM",
        "estimated_hours_min": 3,
        "estimated_hours_max": 4,
        "competency_points": 30,
        "context": "Dung du lieu da lam sach o buoc truoc de xac dinh diem nghen trong phau chuyen doi va truc quan hoa.",
        "scope_included": ["Phan tich phau chuyen doi tu Gio hang den Thanh toan thanh cong."],
        "scope_excluded": [],
        "requires_auto_check": False,
        "requires_mentor_approval": True,
        "mentor_approval_sla_hours": 48,
        "data_privacy_notice": None,
        "inputs": [],
        "outputs": [
            {"sort_order": 1, "description": "Mot bao cao Slide (PDF) toi da 5 trang chi ra 3 diem nghen chinh."},
            {"sort_order": 2, "description": "Mot Dashboard don gian (Tableau Public hoac Looker Studio) truc quan hoa phau chuyen doi (Funnel)."},
        ],
        "criteria": [
            {"criterion": "Xac dinh dung cac Drop-off point trong phau chuyen doi.", "weight_percent": 60},
            {"criterion": "Tinh truc quan va de hieu cua bao cao (Storytelling).", "weight_percent": 40},
        ],
    },
]
