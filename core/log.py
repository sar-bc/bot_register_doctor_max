from database.Database import DataBase
import logging
# from datetime import datetime

class Logger:
    def __init__(self, name_doc):
        self.name_doc = name_doc
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.logger = logging.getLogger(name_doc)

    async def info(self, text: str):
        db = DataBase()
        await db.log_to_db("INFO", text, self.name_doc)
        self.logger.info(text)

    async def error(self, text: str):
        db = DataBase()
        await db.log_to_db("ERROR", text, self.name_doc)
        self.logger.error(text)

    async def warning(self, text: str):
        db = DataBase()
        await db.log_to_db("WARNING", text, self.name_doc)
        self.logger.warning(text)
