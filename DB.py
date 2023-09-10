'''
Avoid importing from utilties
NOTE : conn referes to connection pool,to use DB first create connection pool object in another file 
'''

import os
from utilities import getSite
import psycopg_pool


async def open_pool(pool):
  await pool.open()
  await pool.wait()
  print("Connection Pool Opened")


def create_connection_pool():
  conninfo = os.environ['neon_db_conn']
  pool = psycopg_pool.AsyncConnectionPool(conninfo=conninfo, open=False)
  return pool


async def writeQuery(conn_pool, query, params=None):
  try:
    async with conn_pool.connection() as conn:
      async with conn.cursor() as cursor:
        if params:
          await cursor.execute(query, params)
        else:
          await cursor.execute(query)
        await conn.commit()
  except Exception as e:
    print("Error:", str(e))
    raise


async def readQuery(conn_pool, query, params=None):
  try:
    async with conn_pool.connection() as conn:
      async with conn.cursor() as cursor:
        if params:
          await cursor.execute(query, params)
        else:
          await cursor.execute(query)
        results = await cursor.fetchall()
        return results
  except Exception as e:
    print("Error:", str(e))
    raise


async def refresh_connection_pool(old_pool):
  try:
    # Try running a sample query with the old pool to check if it's responsive
    result = await readQuery(old_pool, 'SELECT 1;')
    if result:
      print("Old Connection Pool is responsive. No need to refresh.")
      return old_pool
  except:
    print("Old pool un-responsive!")

  await old_pool.close()
  # Create a new connection pool
  new_pool = create_connection_pool()
  print("Close Old pool and created new one!")

  return new_pool


async def checkUserDB(conn, tele_id):
  query = f"SELECT EXISTS(SELECT 1 FROM users WHERE tele_id = {tele_id})"
  return await readQuery(conn, query)


async def addUserDB(conn, tele_id, name, username, phone='null'):
  query = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM users WHERE tele_id = {tele_id}) THEN
                INSERT INTO users (tele_id, name, username, phone) VALUES ({tele_id}, '{name}', '{username}', {phone});
            END IF;
        END $$;
    """

  await writeQuery(conn, query)


async def addProductDB(conn, title, url, price):
  # Add product to database
  if not url == 'test':
    site = getSite(url)[0]

  # Check for test notification only admin access command
  query = "SELECT id FROM sites WHERE name = %s;"
  result = await readQuery(conn, query, (site, ))
  siteId = result[0][0]

  insert_query = """
      INSERT INTO products (title, url, site, price)
      VALUES (%s, %s, %s, %s)
      ON CONFLICT (url) DO NOTHING;
  """
  await writeQuery(conn, insert_query, (title, url, siteId, price))


async def getProductsDB(conn, tele_id=None):
  # return product dictionary specific to user
  products = {}

  # if tele_id is specified then return products tracked by that id else return all products
  if tele_id:
    query = f"""
            SELECT TITLE, URL, PRICE, TARGET, T.PRODUCT_ID
            FROM USERS U 
            JOIN TRACKING T ON T.USER_ID=U.USER_ID
            JOIN PRODUCTS P ON T.PRODUCT_ID=P.PRODUCT_ID
            WHERE TELE_ID='{tele_id}';
        """
  else:
    query = "SELECT TITLE, URL, PRICE FROM PRODUCTS P;"

  # here i have set url as key since two products can have same url
  for row in await readQuery(conn, query):
    products[row[1]] = {
      'title': row[0],
      'price': row[2],
      'target': row[3] if tele_id else None,
      'product_id': row[4] if tele_id else None
    }
  return products


async def setTrackingDB(conn, tele_id, url, target):
  # set tracking
  user_query = 'SELECT user_id FROM users WHERE tele_id = %s;'
  user_id = await readQuery(conn, user_query, (tele_id, ))
  user_id = user_id[0][0]

  # check if url is int so that we can directly set product_id without using another query
  if isinstance(url, int):
    # handle retracking
    product_id = url
  else:
    product_query = 'SELECT product_id FROM products WHERE url = %s;'
    product_id = await readQuery(conn, product_query, (url, ))
    product_id = product_id[0][0]

  tracking_query = f"""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM tracking
                WHERE user_id = {user_id} AND product_id = {product_id}
            ) THEN
                INSERT INTO tracking (user_id, product_id, target) VALUES ({user_id}, {product_id}, {target});
            END IF;
        END $$;
    """

  await writeQuery(conn, tracking_query)


async def untrackProductDB(conn, tele_id, product_id):
  query = f'select user_id from users where tele_id={tele_id};'
  user_id = await readQuery(conn, query)
  user_id = user_id[0][0]
  query = f"delete from tracking where user_id={user_id} and product_id={product_id};"
  await writeQuery(conn, query)


async def addLogDB(conn, tele_id, description):
  # to add log
  if tele_id == 677440016:
    return
  query = f"INSERT INTO logs(tele_id,log) VALUES ('{tele_id}', '{description}');"
  await writeQuery(conn, query)


async def showLogsDB(conn):
  # retrive user requests from DB
  query = """select count(tele_id) from logs
    where not tele_id=677440016
    group by tele_id;
    """
  logs = await readQuery(conn, query)
  log_dict = {'Active': 0, 'Passive': 0, 'Ghosts': 0}
  for row in logs:
    if row[0] > 10:
      log_dict['Active'] += 1
    elif row[0] > 2:
      log_dict['Passive'] += 1
    else:
      log_dict['Ghosts'] += 1
  return log_dict
