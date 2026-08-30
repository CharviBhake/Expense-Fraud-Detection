

import random
import numpy as np
import pandas as pd
from faker import Faker
from datetime import datetime, timedelta

fake=Faker()
Faker.seed(42)
random.seed(42)
np.random.seed(42)

N_EMPLOYEES=45
N_VENDORS=18
N_EXPENSES=9000
START_DATE=datetime(2024, 1, 1)
END_DATE=datetime(2025, 6, 30)
FRAUD_RATE=0.035  
DEPARTMENTS=["Sales", "Engineering", "Marketing", "Finance", "Operations",
               "HR", "Legal", "Consulting", "Procurement"]

ROLES_BY_DEPT_LEVEL=["Analyst", "Associate", "Senior Associate", "Manager",
                       "Senior Manager", "Director", "VP"]

CATEGORIES=["Travel", "Meals & Entertainment", "Software & Subscriptions",
              "Office Supplies", "Client Gifts", "Accommodation",
              "Ground Transport", "Conference & Training", "Miscellaneous"]

APPROVAL_THRESHOLDS={
    "Travel": 15000, "Meals & Entertainment": 5000, "Software & Subscriptions": 20000,
    "Office Supplies": 3000,"Client Gifts": 8000, "Accommodation": 12000,
    "Ground Transport": 3000, "Conference & Training": 25000,"Miscellaneous": 5000,
}

CATEGORY_AMOUNT_DIST={
    "Travel": (8000, 3500),"Meals & Entertainment": (1800, 900),
    "Software & Subscriptions":(6000, 4000), "Office Supplies": (1200, 700),
    "Client Gifts": (3500, 1800), "Accommodation": (7000, 3000),
    "Ground Transport": (900, 500),"Conference & Training": (12000, 5000),
    "Miscellaneous": (1500, 1000),
}

VENDOR_CATEGORY_MAP ={
    "Travel": ["MakeMyTrip Corporate", "ClearTrip Biz", "Yatra Business"],
    "Meals & Entertainment": ["Zomato for Business", "Swiggy Genie", "The Leela Catering"],
    "Software & Subscriptions": ["AWS", "Microsoft Azure", "Adobe", "Slack", "Zoom", "Notion"],
    "Office Supplies": ["Staples India", "Amazon Business", "Office Depot"],
    "Client Gifts": ["Ferns N Petals Corporate", "Amazon Business"],
    "Accommodation": ["Taj Hotels", "OYO Business", "Marriott Corporate"],
    "Ground Transport": ["Uber for Business", "Ola Corporate"],
    "Conference & Training": ["Coursera Business", "Eventbrite", "Udemy Business"],
    "Miscellaneous": ["Amazon Business", "Local Vendor"],
}

employees=[]
for eid in range(1, N_EMPLOYEES + 1):
    dept=random.choice(DEPARTMENTS)
    role=random.choices(ROLES_BY_DEPT_LEVEL, weights=[30,25,20,12,7,4,2])[0]
    join_date=fake.date_between(start_date="-6y",end_date="-3m")
    employees.append({
        "employee_id":eid,
        "name":fake.name(),
        "department":dept,
        "role":role,
        "manager_id":None,  
        "join_date":join_date,
    })

emp_df=pd.DataFrame(employees)
role_rank={r:i for i,r in enumerate(ROLES_BY_DEPT_LEVEL)}
for i, row in emp_df.iterrows():
    same_dept_higher=emp_df[(emp_df.department == row.department) &
                               (emp_df.role.map(role_rank) > role_rank[row.role])]
    if len(same_dept_higher) >0:
        emp_df.at[i, "manager_id"]=int(same_dept_higher.sample(1).employee_id.values[0])

vendor_rows=[]
vid=1
seen=set()
for cat, names in VENDOR_CATEGORY_MAP.items():
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        vendor_rows.append({"vendor_id":vid, "vendor_name": name, "category": cat})
        vid += 1
vendor_df=pd.DataFrame(vendor_rows)

def vendor_for_category(cat):
    opts=vendor_df[vendor_df.category == cat]
    return opts.sample(1).iloc[0]

def random_datetime(start, end):
    delta = end-start
    return start+timedelta(seconds=random.randint(0, int(delta.total_seconds())))

emp_avg_by_cat={}

expenses=[]
expense_id=1
n_normal=int(N_EXPENSES * (1- FRAUD_RATE))

for _ in range(n_normal):
    emp=emp_df.sample(1).iloc[0]
    cat=random.choices(CATEGORIES, weights=[15, 20, 10, 12, 5, 8, 15, 8, 7])[0]
    vendor=vendor_for_category(cat)
    mean, std=CATEGORY_AMOUNT_DIST[cat]
    amount=max(200, round(np.random.normal(mean, std), 2))
    expense_date=random_datetime(START_DATE, END_DATE)

    submission_delay_days=np.random.gamma(2, 2) 
    submission_date=expense_date + timedelta(days=submission_delay_days)
    if submission_date>END_DATE:
        submission_date=END_DATE

    threshold=APPROVAL_THRESHOLDS[cat]
    receipt_attached=random.random() > 0.04  

    expenses.append({
        "expense_id": expense_id,
        "employee_id":emp.employee_id,
        "vendor_id":vendor.vendor_id,
        "amount":amount,
        "category":cat,
        "submission_date":submission_date,
        "expense_date":expense_date.date(),
        "approved_by":emp.manager_id if pd.notna(emp.manager_id) else emp.employee_id,
        "approval_status":random.choices(["Approved", "Pending", "Rejected"], weights=[92, 6, 2])[0],
        "receipt_attached":receipt_attached,
        "description":fake.sentence(nb_words=6),
        "is_fraud_injected": "none",
    })
    expense_id+=1

fraud_expenses=[]
n_fraud_total=N_EXPENSES-n_normal
n_per_pattern=n_fraud_total 

repeat_offenders=emp_df.sample(6,random_state=1).employee_id.tolist()

def base_expense_row(emp_id,cat,amount,expense_date,submission_date,
        receipt_attached,tag,vendor_id=None):
    global expense_id
    if vendor_id is None:
        vendor_id = vendor_for_category(cat).vendor_id
    emp=emp_df[emp_df.employee_id == emp_id].iloc[0]
    row = {
        "expense_id": expense_id,
        "employee_id": emp_id,
        "vendor_id": vendor_id,
        "amount": amount,
        "category": cat,
        "submission_date": submission_date,
        "expense_date": expense_date.date() if hasattr(expense_date, "date") else expense_date,
        "approved_by": emp.manager_id if pd.notna(emp.manager_id) else emp.employee_id,
        "approval_status": random.choices(["Approved", "Pending"], weights=[85, 15])[0],
        "receipt_attached": receipt_attached,
        "description": fake.sentence(nb_words=6),
        "is_fraud_injected": tag,
    }
    expense_id +=1
    return row

for _ in range(n_per_pattern):
    emp=random.choice(repeat_offenders)
    cat=random.choice(CATEGORIES)
    vendor=vendor_for_category(cat)
    mean,std=CATEGORY_AMOUNT_DIST[cat]
    amount=max(200, round(np.random.normal(mean, std), 2))
    exp_date=random_datetime(START_DATE, END_DATE)
    sub_date1=exp_date + timedelta(days=1)
    sub_date2=sub_date1 + timedelta(days=random.randint(2, 6))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date1, True, "duplicate", vendor.vendor_id))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date2, True, "duplicate", vendor.vendor_id))

for _ in range(n_per_pattern):
    emp=emp_df.sample(1).iloc[0].employee_id
    cat=random.choice(CATEGORIES)
    amount=random.choice([2000, 5000, 10000, 15000, 20000, 25000])
    exp_date=random_datetime(START_DATE, END_DATE)
    sub_date=exp_date + timedelta(days=random.randint(0, 3))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, random.random() > 0.3, "round_number"))

for _ in range(n_per_pattern):
    emp=emp_df.sample(1).iloc[0].employee_id
    cat=random.choice(CATEGORIES)
    threshold=APPROVAL_THRESHOLDS[cat]
    amount=round(threshold * random.uniform(0.96, 0.999), 2)
    exp_date=random_datetime(START_DATE, END_DATE)
    sub_date=exp_date + timedelta(days=random.randint(0, 3))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, True, "threshold_skirting"))

for _ in range(n_per_pattern):
    emp =random.choice(repeat_offenders)
    cat =random.choice(CATEGORIES)
    mean, std =CATEGORY_AMOUNT_DIST[cat]
    amount =max(200, round(np.random.normal(mean, std), 2))
    exp_date=random_datetime(START_DATE, END_DATE)
    while exp_date.weekday() < 5:
        exp_date = random_datetime(START_DATE, END_DATE)
    sub_date = exp_date + timedelta(hours=random.randint(1, 20))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, random.random() > 0.5, "weekend_spike"))


kickback_vendor=vendor_df.sample(1).iloc[0]
kickback_employees=repeat_offenders[:2]
for _ in range(n_per_pattern):
    emp =random.choice(kickback_employees)
    cat= kickback_vendor.category
    mean, std= CATEGORY_AMOUNT_DIST.get(cat, (5000, 2000))
    amount=max(500, round(np.random.normal(mean * 1.8, std), 2))  # unusually high amounts
    exp_date=random_datetime(START_DATE, END_DATE)
    sub_date=exp_date + timedelta(days=random.randint(0, 3))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, random.random() > 0.4,
                     "vendor_concentration", kickback_vendor.vendor_id))


for _ in range(n_per_pattern):
    emp=emp_df.sample(1).iloc[0].employee_id
    cat=random.choice(CATEGORIES)
    mean,std=CATEGORY_AMOUNT_DIST[cat]
    amount=max(500, round(np.random.normal(mean * 2.2, std), 2))  # unusually high
    exp_date=random_datetime(START_DATE, END_DATE)
    sub_date=exp_date+timedelta(days=random.randint(0, 5))
    fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, False, "missing_receipt_high_amount"))

for _ in range(n_per_pattern):
    emp=random.choice(repeat_offenders)
    cat=random.choice(CATEGORIES)
    threshold=APPROVAL_THRESHOLDS[cat]
    n_splits =random.choice([2, 3])
    exp_date= random_datetime(START_DATE, END_DATE)
    vendor =vendor_for_category(cat)
    for i in range(n_splits):
        amount= round((threshold*random.uniform(0.8, 0.95)) / n_splits, 2)
        sub_date =exp_date +timedelta(hours=random.randint(0, 48))
        fraud_expenses.append(base_expense_row(emp, cat, amount, exp_date, sub_date, True, "split_transaction", vendor.vendor_id))

exp_df=pd.DataFrame(expenses+fraud_expenses)
exp_df=exp_df.sample(frac=1,random_state=7).reset_index(drop=True)
exp_df["expense_id"] =range(1, len(exp_df) + 1)  

emp_df.to_csv("/home/claude/employees.csv", index=False)
vendor_df.to_csv("/home/claude/vendors.csv", index=False)
exp_df.to_csv("/home/claude/expenses.csv", index=False)

print(f"Employees: {len(emp_df)}")
print(f"Vendors:   {len(vendor_df)}")
print(f"Expenses:  {len(exp_df)}  (fraud-injected: {(exp_df.is_fraud_injected != 'none').sum()}, "
      f"{(exp_df.is_fraud_injected != 'none').mean()*100:.1f}%)")
print("\nFraud pattern breakdown:")
print(exp_df[exp_df.is_fraud_injected != "none"].is_fraud_injected.value_counts())
