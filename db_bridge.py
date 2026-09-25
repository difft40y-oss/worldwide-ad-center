import asyncio
from databases import Database

# Pointing straight down the encrypted local SSH tunnel mapping vector
DATABASE_URL = "postgresql+asyncpg://database_user:secure_password@127.0.0.1:5432/worldwide_ad_center?ssl=prefer"
database = Database(DATABASE_URL, min_size=2, max_size=5)

async def insert_ad_record_to_cloud(title: str, category: str, metadata_dict: dict):
    try:
        await database.connect()
        # Direct structural injection target mapping the master operational tables
        query = """
            INSERT INTO ads_master (title, category, is_trial_active) 
            VALUES (:title, :category, true) 
            RETURNING ad_id;
        """
        ad_id = await database.execute(query=query, values={"title": title, "category": category})
        print(f"[Cloud DB Proxy] Record successfully stored in remote cluster. Ad UUID Reference: {ad_id}")
        return ad_id
    except Exception as e:
        print(f"[Cloud DB Proxy] Error connecting via tunnel bridge: {str(e)}")
        return None
    finally:
        await database.disconnect()

if __name__ == "__main__":
    asyncio.run(insert_ad_record_to_cloud("Redmi 13 Campaign", "Product Launch", {}))
