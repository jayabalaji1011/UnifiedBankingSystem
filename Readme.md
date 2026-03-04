# UnifiedBankingSystem 💳🏦

UnifiedBankingSystem is a full-stack digital banking and UPI payment simulation project built using Django.  
The system replicates real-world banking workflows including KYC verification, ATM management, and secure digital transactions.

---

## 📌 Project Modules

The system is divided into five Django apps:

- **Aadhaar** – Stores and verifies user identity details  
- **PAN** – PAN creation with Aadhaar verification and 18+ age validation  
- **DigitalBank** – Core banking operations handled by staff and Customer account management 
- **YourBank** – Core banking operations handled by staff and Customer account management  
- **UPay** – UPI-based digital payment system  

---

## 🔐 Key Features

### ✅ Identity & KYC
- Aadhaar as primary identity
- PAN creation requires valid Aadhaar
- Age validation (18+ rule)
- KYC required for bank account creation

### ✅ Banking System (Staff Side)
- Bank account creation after verification
- Account activation / deactivation
- Deposit & Withdraw
- Same-bank transfers
- Transaction history tracking

### ✅ ATM Card Management
- ATM card issuance after account creation
- PIN generation and change
- Card block / unblock
- Card renewal

### ✅ UPay – Digital Payment
- Login using Mobile Number + OTP
- Bank account linking via Aadhaar or Debit Card
- Money transfer using mobile number or account number
- UPI PIN authentication
- Balance check and transaction history

---

## 🛡 Security Features

- OTP-based authentication
- UPI PIN validation
- ATM PIN protection
- Role-based access (Admin / Staff / Customer)

---

## 🛠 Technologies Used

- Python
- Django
- SQLite
- HTML
- CSS
- Bootstrap
- Basic JavaScript

---

## 🚀 Installation Guide

1. Clone the repository:https://github.com/jayabalaji1011/UnifiedBankingSystem
