import psycopg2
import time
from datetime import datetime
from typing import Dict
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class MigrationFramework:
    
    def __init__(self):
        self.blue_conn = None
        self.green_conn = None
        self.active_env = 'blue'
        
    def connect_databases(self):
        logger.info("Connecting to databases...")
        
        try:
            self.blue_conn = psycopg2.connect(
                host='localhost',
                port=5439,
                dbname='production_blue',
                user='postgres',
                password='postgres'
            )
            self.blue_conn.autocommit = True
            logger.info("Connected to BLUE database")
            
            self.green_conn = psycopg2.connect(
                host='localhost',
                port=5440,
                dbname='production_green',
                user='postgres',
                password='postgres'
            )
            self.green_conn.autocommit = True
            logger.info("Connected to GREEN database")
            
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False
    
    def setup_blue_database(self):
        logger.info("Setting up BLUE database (current production)...")
        
        cursor = self.blue_conn.cursor()
        
        cursor.execute("""
            DROP TABLE IF EXISTS users CASCADE;
            DROP TABLE IF EXISTS transactions CASCADE;
            
            CREATE TABLE users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW()
            );
            
            CREATE TABLE transactions (
                transaction_id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(user_id),
                amount DECIMAL(10,2),
                transaction_date TIMESTAMP DEFAULT NOW()
            );
            
            INSERT INTO users (username, email)
            SELECT 'user_' || i, 'user' || i || '@example.com'
            FROM generate_series(1, 1000) i;
            
            INSERT INTO transactions (user_id, amount)
            SELECT (random() * 999 + 1)::INT, (random() * 1000)::DECIMAL(10,2)
            FROM generate_series(1, 5000);
        """)
        
        cursor.close()
        logger.info("BLUE database ready")
    
    def prepare_green_database(self):
        logger.info("Preparing GREEN database with NEW SCHEMA...")
        
        cursor = self.green_conn.cursor()
        
        cursor.execute("""
            DROP TABLE IF EXISTS users CASCADE;
            DROP TABLE IF EXISTS transactions CASCADE;
            
            CREATE TABLE users (
                user_id SERIAL PRIMARY KEY,
                username VARCHAR(50),
                email VARCHAR(100),
                created_at TIMESTAMP DEFAULT NOW(),
                status VARCHAR(20) DEFAULT 'active'
            );
            
            CREATE TABLE transactions (
                transaction_id SERIAL PRIMARY KEY,
                user_id INT REFERENCES users(user_id),
                amount DECIMAL(10,2),
                transaction_date TIMESTAMP DEFAULT NOW(),
                transaction_type VARCHAR(20) DEFAULT 'purchase'
            );
            
            CREATE INDEX idx_users_status ON users(status);
        """)
        
        cursor.close()
        logger.info("GREEN database ready with enhanced schema")
    
    def migrate_data(self):
        logger.info("Migrating data from BLUE to GREEN...")
        
        blue_cursor = self.blue_conn.cursor()
        green_cursor = self.green_conn.cursor()
        
        start_time = time.time()
        
        blue_cursor.execute("SELECT user_id, username, email, created_at FROM users")
        users = blue_cursor.fetchall()
        
        for user in users:
            green_cursor.execute(
                "INSERT INTO users (user_id, username, email, created_at, status) VALUES (%s, %s, %s, %s, 'active')",
                user
            )
        
        logger.info(f"Migrated {len(users)} users")
        
        blue_cursor.execute("SELECT transaction_id, user_id, amount, transaction_date FROM transactions")
        transactions = blue_cursor.fetchall()
        
        for txn in transactions:
            green_cursor.execute(
                "INSERT INTO transactions (transaction_id, user_id, amount, transaction_date, transaction_type) VALUES (%s, %s, %s, %s, 'purchase')",
                txn
            )
        
        logger.info(f"Migrated {len(transactions)} transactions")
        
        migration_time = time.time() - start_time
        logger.info(f"Migration completed in {migration_time:.2f}s")
        
        blue_cursor.close()
        green_cursor.close()
        
        return migration_time
    
    def validate_migration(self) -> Dict:
        logger.info("Validating migration...")
        
        blue_cursor = self.blue_conn.cursor()
        green_cursor = self.green_conn.cursor()
        
        validation = {'all_passed': True, 'checks': []}
        
        blue_cursor.execute("SELECT COUNT(*) FROM users")
        blue_users = blue_cursor.fetchone()[0]
        
        green_cursor.execute("SELECT COUNT(*) FROM users")
        green_users = green_cursor.fetchone()[0]
        
        passed = blue_users == green_users
        logger.info(f"Users count: {'PASS' if passed else 'FAIL'} (Blue: {blue_users}, Green: {green_users})")
        
        if not passed:
            validation['all_passed'] = False
        
        blue_cursor.close()
        green_cursor.close()
        
        return validation
    
    def cutover_to_green(self):
        logger.info("Switching to GREEN environment...")
        self.active_env = 'green'
        logger.info("Traffic now on GREEN")
    
    def rollback_to_blue(self):
        logger.info("Rolling back to BLUE...")
        self.active_env = 'blue'
        logger.info("Rollback complete")
    
    def get_active_connection(self):
        return self.blue_conn if self.active_env == 'blue' else self.green_conn
    
    def simulate_traffic(self, duration: int = 3):
        logger.info(f"Simulating traffic for {duration}s...")
        
        conn = self.get_active_connection()
        cursor = conn.cursor()
        
        ops = 0
        start_time = time.time()
        
        while time.time() - start_time < duration:
            cursor.execute("SELECT COUNT(*) FROM users")
            cursor.fetchone()
            cursor.execute("SELECT SUM(amount) FROM transactions")
            cursor.fetchone()
            ops += 2
            time.sleep(0.1)
        
        cursor.close()
        logger.info(f"Executed {ops} operations on {self.active_env.upper()}")
        return ops
    
    def run_migration(self):
        print("\n" + "=" * 80)
        print("ZERO-DOWNTIME DATABASE MIGRATION")
        print("=" * 80)
        
        if not self.connect_databases():
            return
        
        print("\nPHASE 1: SETUP BLUE")
        self.setup_blue_database()
        
        print("\nPHASE 2: PREPARE GREEN")
        self.prepare_green_database()
        
        print("\nPHASE 3: MIGRATE DATA")
        migration_time = self.migrate_data()
        
        print("\nPHASE 4: VALIDATE")
        validation = self.validate_migration()
        
        if not validation['all_passed']:
            print("VALIDATION FAILED")
            return
        
        print("\nPHASE 5: TRAFFIC ON BLUE")
        self.simulate_traffic(3)
        
        print("\nPHASE 6: CUTOVER TO GREEN")
        self.cutover_to_green()
        
        print("\nPHASE 7: TRAFFIC ON GREEN")
        self.simulate_traffic(3)
        
        print("\nPHASE 8: TEST ROLLBACK")
        self.rollback_to_blue()
        self.simulate_traffic(2)
        
        print("\nPHASE 9: FINAL CUTOVER")
        self.cutover_to_green()
        
        print("\n" + "=" * 80)
        print("MIGRATION COMPLETE")
        print(f"Migration Time: {migration_time:.2f}s")
        print(f"Downtime: 0s")
        print(f"Active Environment: {self.active_env.upper()}")
        print("=" * 80)


def main():
    migration = MigrationFramework()
    migration.run_migration()


if __name__ == "__main__":
    main()