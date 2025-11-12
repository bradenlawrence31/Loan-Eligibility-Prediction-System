import oracledb
import numpy as np
from datetime import datetime


class LoanEligibilityCalculator:
    def __init__(self):
        self.connection = None
        self.cursor = None

    def connect_database(self):
        """Connect to Oracle 19c database (manual credentials)"""
        try:
            # 🔽 Type your Oracle username, password, and DSN manually here
            username = "c##ronny"
            password = "1234"
            dsn = "localhost:1521/orcldb"  # Example DSN – edit if different

            self.connection = oracledb.connect(
                user=username,
                password=password,
                dsn=dsn
            )
            self.cursor = self.connection.cursor()
            print("Successfully connected to Oracle Database")
            return True
        except oracledb.Error as error:
            print(f"Error connecting to database: {error}")
            return False

    def setup_database(self):
        """Create necessary tables for loan calculator"""
        try:
            self.cursor.execute("""
                CREATE TABLE interest_rates (
                    rate_id NUMBER PRIMARY KEY,
                    loan_tenure_years NUMBER NOT NULL,
                    interest_rate NUMBER(5,2) NOT NULL,
                    effective_date DATE DEFAULT SYSDATE
                )
            """)

            self.cursor.execute("""
                CREATE TABLE loan_applications (
                    application_id NUMBER PRIMARY KEY,
                    applicant_name VARCHAR2(100) NOT NULL,
                    monthly_income NUMBER(12,2) NOT NULL,
                    loan_tenure_years NUMBER NOT NULL,
                    interest_rate NUMBER(5,2) NOT NULL,
                    eligible_amount NUMBER(12,2),
                    monthly_emi NUMBER(12,2),
                    application_date DATE DEFAULT SYSDATE,
                    is_eligible VARCHAR2(3)
                )
            """)

            # Create sequences
            self.cursor.execute("""
                CREATE SEQUENCE loan_app_seq START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE
            """)
            self.cursor.execute("""
                CREATE SEQUENCE rate_seq START WITH 1 INCREMENT BY 1 NOCACHE NOCYCLE
            """)

            # Insert default interest rates
            interest_data = [
                (1, 8.5), (2, 9.0), (3, 9.5),
                (5, 10.0), (7, 10.5), (10, 11.0),
                (15, 11.5), (20, 12.0)
            ]
            for tenure, rate in interest_data:
                self.cursor.execute("""
                    INSERT INTO interest_rates (rate_id, loan_tenure_years, interest_rate)
                    VALUES (rate_seq.NEXTVAL, :1, :2)
                """, (tenure, rate))

            self.connection.commit()
            print("Database setup completed successfully")

        except oracledb.Error as error:
            print(f"Error setting up database: {error}")
            self.connection.rollback()

    def get_interest_rate(self, tenure_years):
        try:
            self.cursor.execute("""
                SELECT interest_rate FROM interest_rates WHERE loan_tenure_years = :1
            """, (tenure_years,))
            result = self.cursor.fetchone()
            if result:
                return result[0]
            else:
                self.cursor.execute("""
                    SELECT interest_rate 
                    FROM interest_rates 
                    WHERE loan_tenure_years >= :1
                    ORDER BY loan_tenure_years
                    FETCH FIRST 1 ROWS ONLY
                """, (tenure_years,))
                result = self.cursor.fetchone()
                return result[0] if result else 12.0
        except oracledb.Error as error:
            print(f"Error fetching interest rate: {error}")
            return 12.0

    def calculate_emi(self, principal, annual_rate, tenure_years):
        monthly_rate = annual_rate / (12 * 100)
        num_payments = tenure_years * 12

        if monthly_rate == 0:
            emi = principal / num_payments
        else:
            emi = principal * monthly_rate * np.power(1 + monthly_rate, num_payments) / \
                  (np.power(1 + monthly_rate, num_payments) - 1)
        return float(emi)

    def calculate_eligibility(self, monthly_income, tenure_years):
        interest_rate = self.get_interest_rate(tenure_years)
        max_emi = monthly_income * 0.50
        monthly_rate = interest_rate / (12 * 100)
        num_payments = tenure_years * 12

        if monthly_rate == 0:
            eligible_amount = max_emi * num_payments
        else:
            eligible_amount = max_emi * (np.power(1 + monthly_rate, num_payments) - 1) / \
                              (monthly_rate * np.power(1 + monthly_rate, num_payments))

        actual_emi = self.calculate_emi(eligible_amount, interest_rate, tenure_years)
        return {
            'eligible_amount': float(eligible_amount),
            'monthly_emi': float(actual_emi),
            'interest_rate': interest_rate,
            'total_payment': float(actual_emi * num_payments),
            'total_interest': float((actual_emi * num_payments) - eligible_amount)
        }

    def save_application(self, name, monthly_income, tenure_years, eligibility_data):
        try:
            is_eligible = 'YES' if eligibility_data['eligible_amount'] >= 50000 else 'NO'
            self.cursor.execute("""
                INSERT INTO loan_applications (
                    application_id, applicant_name, monthly_income, 
                    loan_tenure_years, interest_rate, eligible_amount,
                    monthly_emi, is_eligible
                ) VALUES (
                    loan_app_seq.NEXTVAL, :1, :2, :3, :4, :5, :6, :7
                )
            """, (name, monthly_income, tenure_years,
                  eligibility_data['interest_rate'],
                  eligibility_data['eligible_amount'],
                  eligibility_data['monthly_emi'],
                  is_eligible))
            self.connection.commit()
            print("\n✓ Application saved successfully!")
        except oracledb.Error as error:
            print(f"Error saving application: {error}")
            self.connection.rollback()

    def display_results(self, eligibility_data, monthly_income):
        print("\n" + "=" * 60)
        print("LOAN ELIGIBILITY RESULTS")
        print("=" * 60)
        print(f"Monthly Income:           ₹{monthly_income:,.2f}")
        print(f"Interest Rate:            {eligibility_data['interest_rate']:.2f}%")
        print(f"Eligible Loan Amount:     ₹{eligibility_data['eligible_amount']:,.2f}")
        print(f"Monthly EMI:              ₹{eligibility_data['monthly_emi']:,.2f}")
        print(f"Total Amount Payable:     ₹{eligibility_data['total_payment']:,.2f}")
        print(f"Total Interest:           ₹{eligibility_data['total_interest']:,.2f}")
        print("=" * 60)

        if eligibility_data['eligible_amount'] >= 50000:
            print("✓ You are ELIGIBLE for a personal loan!")
        else:
            print("✗ Loan amount too low. Minimum eligible amount is ₹50,000")

    def view_all_applications(self):
        try:
            self.cursor.execute("""
                SELECT applicant_name, monthly_income, loan_tenure_years,
                       eligible_amount, monthly_emi, is_eligible,
                       TO_CHAR(application_date, 'DD-MON-YYYY')
                FROM loan_applications
                ORDER BY application_date DESC
            """)
            results = self.cursor.fetchall()
            if results:
                print("\n" + "=" * 100)
                print("ALL LOAN APPLICATIONS")
                print("=" * 100)
                print(
                    f"{'Name':<20} {'Income':<15} {'Tenure':<10} {'Eligible Amt':<18} {'EMI':<15} {'Status':<10} {'Date':<12}")
                print("-" * 100)
                for row in results:
                    print(
                        f"{row[0]:<20} ₹{row[1]:>13,.2f} {row[2]:>8} yrs ₹{row[3]:>15,.2f} ₹{row[4]:>13,.2f} {row[5]:<10} {row[6]:<12}")
                print("=" * 100)
            else:
                print("\nNo applications found in database.")
        except oracledb.Error as error:
            print(f"Error fetching applications: {error}")

    def run(self):
        """Main application loop"""
        print("\n" + "=" * 60)
        print("PERSONAL LOAN ELIGIBILITY CALCULATOR")
        print("=" * 60)

        # 🔹 Directly connect without user input
        if not self.connect_database():
            return

        setup = input("\nFirst time setup? (yes/no): ").lower()
        if setup == 'yes':
            self.setup_database()

        while True:
            print("\n" + "-" * 60)
            print("MENU")
            print("-" * 60)
            print("1. Calculate Loan Eligibility")
            print("2. View All Applications")
            print("3. Exit")

            choice = input("\nEnter your choice (1-3): ")

            if choice == '1':
                try:
                    name = input("\nEnter applicant name: ")
                    monthly_income = float(input("Enter monthly income (₹): "))
                    tenure_years = int(input("Enter loan tenure (years): "))

                    if monthly_income <= 0 or tenure_years <= 0:
                        print("Invalid input! Income and tenure must be positive.")
                        continue

                    eligibility_data = self.calculate_eligibility(monthly_income, tenure_years)
                    self.display_results(eligibility_data, monthly_income)

                    save = input("\nSave this application? (yes/no): ").lower()
                    if save == 'yes':
                        self.save_application(name, monthly_income, tenure_years, eligibility_data)
                except ValueError:
                    print("Invalid input! Please enter numeric values.")
                except Exception as e:
                    print(f"Error: {e}")
            elif choice == '2':
                self.view_all_applications()
            elif choice == '3':
                print("\nThank you for using Loan Eligibility Calculator!")
                break
            else:
                print("Invalid choice! Please select 1-3.")

        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()


if __name__ == "__main__":
    calculator = LoanEligibilityCalculator()
    calculator.run()
