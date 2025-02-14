import random
from datetime import timedelta
import pandas as pd
import duckdb
from faker import Faker

class FakeDataGenerator:
    """
    A class to generate fake data for goLance tables ensuring logical consistency.
    """
    def __init__(self, num_jobs=100, max_applications_per_job=10, num_freelancers=50, num_clients=20, seed=42):
        self.num_jobs = num_jobs
        self.max_applications_per_job = max_applications_per_job
        self.num_freelancers = num_freelancers
        self.num_clients = num_clients
        self.faker = Faker()
        Faker.seed(seed)
        random.seed(seed)
        self.categories = [
            "Web Development", "Marketing", "Graphic Design",
            "Writing", "Data Science", "Mobile Development"
        ]

    def generate_jobs(self):
        """
        Generate a list of jobs with logically consistent dates and statuses.
        """
        jobs_data = []
        for job_id in range(1, self.num_jobs + 1):
            category = random.choice(self.categories)
            posted_at = self.faker.date_time_between(start_date='-1y', end_date='now')
            client_id = random.randint(1, self.num_clients)
            status = random.choices(["filled", "open", "expired"], weights=[0.6, 0.2, 0.2])[0]

            if status == "filled":
                min_delta = timedelta(hours=1)
                max_delta = timedelta(days=30)
                delta_seconds = random.randint(int(min_delta.total_seconds()), int(max_delta.total_seconds()))
                filled_at = posted_at + timedelta(seconds=delta_seconds)
            else:
                filled_at = None

            jobs_data.append({
                "job_id": job_id,
                "category": category,
                "posted_at": posted_at,
                "filled_at": filled_at,
                "client_id": client_id,
                "status": status
            })
        return jobs_data

    def generate_applications(self, jobs_data):
        """
        Generate freelancer applications for each job.
        For filled jobs, exactly one application is accepted.
        For open/expired jobs, applications are either pending or rejected.
        """
        applications_data = []
        application_id = 1
        for job in jobs_data:
            job_id = job["job_id"]
            posted_at = job["posted_at"]
            filled_at = job["filled_at"]
            job_status = job["status"]

            num_applications = random.randint(1, self.max_applications_per_job)
            freelancers_applying = random.sample(
                range(1, self.num_freelancers + 1),
                min(num_applications, self.num_freelancers)
            )

            accepted_index = random.choice(range(len(freelancers_applying))) if job_status == "filled" else None

            for i, freelancer_id in enumerate(freelancers_applying):
                if job_status == "filled" and filled_at is not None:
                    applied_at = self.faker.date_time_between_dates(
                        datetime_start=posted_at,
                        datetime_end=filled_at
                    )
                else:
                    applied_at = self.faker.date_time_between(start_date=posted_at, end_date='now')

                if job_status == "filled":
                    app_status = "accepted" if i == accepted_index else "rejected"
                else:
                    app_status = random.choice(["pending", "rejected"])

                applications_data.append({
                    "application_id": application_id,
                    "job_id": job_id,
                    "freelancer_id": freelancer_id,
                    "applied_at": applied_at,
                    "status": app_status
                })
                application_id += 1

        return applications_data

    def generate_contracts(self, jobs_data, applications_data):
        """
        Generate contracts only for jobs that are filled and have an accepted application.
        The contract start_date is generated to be after the job's filled_at date.
        """
        contracts_data = []
        contract_id = 1
        accepted_mapping = {}
        for app in applications_data:
            if app["status"] == "accepted":
                accepted_mapping[app["job_id"]] = {
                    "freelancer_id": app["freelancer_id"],
                    "applied_at": app["applied_at"]
                }

        for job in jobs_data:
            job_id = job["job_id"]
            if job["status"] == "filled" and job_id in accepted_mapping:
                freelancer_id = accepted_mapping[job_id]["freelancer_id"]
                start_date = self.faker.date_time_between_dates(
                    datetime_start=job["filled_at"],
                    datetime_end=job["filled_at"] + timedelta(days=10)
                )
                contracts_data.append({
                    "contract_id": contract_id,
                    "freelancer_id": freelancer_id,
                    "job_id": job_id,
                    "start_date": start_date
                })
                contract_id += 1

        return contracts_data

    def load_to_duckdb(self, jobs_data, applications_data, contracts_data):
        """
        Convert the data to Pandas DataFrames and load them into DuckDB tables.
        """
        jobs_df = pd.DataFrame(jobs_data)
        applications_df = pd.DataFrame(applications_data)
        contracts_df = pd.DataFrame(contracts_data)

        con = duckdb.connect("goLance_data.db")

        con.execute("""
            CREATE TABLE jobs (
                job_id INTEGER,
                category TEXT,
                posted_at TIMESTAMP,
                filled_at TIMESTAMP,
                client_id INTEGER,
                status TEXT
            )
        """)

        con.execute("""
            CREATE TABLE freelancer_applications (
                application_id INTEGER,
                job_id INTEGER,
                freelancer_id INTEGER,
                applied_at TIMESTAMP,
                status TEXT
            )
        """)

        con.execute("""
            CREATE TABLE freelancer_contracts (
                contract_id INTEGER,
                freelancer_id INTEGER,
                job_id INTEGER,
                start_date TIMESTAMP
            )
        """)

        con.register("jobs_df", jobs_df)
        con.execute("INSERT INTO jobs SELECT * FROM jobs_df")
        con.unregister("jobs_df")

        con.register("applications_df", applications_df)
        con.execute("INSERT INTO freelancer_applications SELECT * FROM applications_df")
        con.unregister("applications_df")

        con.register("contracts_df", contracts_df)
        con.execute("INSERT INTO freelancer_contracts SELECT * FROM contracts_df")
        con.unregister("contracts_df")

        print("Data successfully loaded into DuckDB tables: jobs, freelancer_applications, freelancer_contracts.")
        return con

def main():
    generator = FakeDataGenerator(
        num_jobs=1000,
        max_applications_per_job=30,
        num_freelancers=2000,
        num_clients=200,
        seed=42
    )

    jobs_data = generator.generate_jobs()
    applications_data = generator.generate_applications(jobs_data)
    contracts_data = generator.generate_contracts(jobs_data, applications_data)

    duckdb_con = generator.load_to_duckdb(jobs_data, applications_data, contracts_data)

    result = duckdb_con.execute("SELECT COUNT(*) FROM jobs").fetchall()
    print("Number of jobs in the database:", result[0][0])

if __name__ == "__main__":
    main()
