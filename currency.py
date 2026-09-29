print("--- Advanced Nepal Exchange Engine ---")
print("1. USD to NPR ($)")
print("2. EUR to NPR (e)")
choice = input("Select Option (1 or 2): ")
amount = float(input("Enter Amount to Convert: "))

if choice == "1":
    res = amount * 135.50
    print("Amount in Nepali Rupees: Rs", res)
else:
    res = amount * 143.20
    print("Amount in Nepali Rupees: Rs", res)



