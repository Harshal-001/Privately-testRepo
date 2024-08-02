import json
import sys

import psycopg2
from psycopg2 import sql
import random
import string
import datetime

# Database connection parameters
DB_NAME = 'demodb'
DB_USER = 'postgres'
DB_PASSWORD = 'MyPass'
DB_HOST = 'localhost'
DB_PORT = '5432'

def serialize_datetime(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat(sep=' ')
    raise TypeError("Type not serializable")

stringSet = set()

conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
    )
cur = conn.cursor()

def generate_unique_strings(n, l):
    """
    Generate a list of n unique strings, each l characters long.

    Parameters:
    n (int): The number of unique strings to generate.
    l (int): The length of the generated strings.

    Returns:
    list: A list of unique strings.
    """

    cl = len(stringSet) + n
    tl = list()

    while len(stringSet) < cl:
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=l))
        m = len(stringSet)
        stringSet.add(code)
        if(len(stringSet) == m+1):
            tl.append(code)
    return tl


def authorize(session_id, session_password):
    """
    Authorize the session by checking the session_id and password in the sessionInfo table.

    Parameters:
    session_username (str): The session username to check.
    session_password (str): The session password to check.

    Returns:
    str: Retailer_id if the session is authorized, otherwise None.
    """

    cur.execute("""
    SELECT retailer_id 
    FROM auth.sessionInfo 
    WHERE session_id = %s AND session_password = %s
    """, (session_id, session_password))

    result = cur.fetchone()

    if result:
        return result[0]
    else:
        return None


def login(username):
    """
    Perform the login operation by searching for the username in the Retailer_Account table.
    If found, generate a temporary session username and password, insert them into the authInfo table,
    and return the generated username and password.

    Parameters:
    username (str): The username to search for.

    Returns:
    dict: A dict containing the generated session_id and password if the username is found, otherwise None.
    """

    cur.execute("SELECT retailer_id FROM baseschema.RetailerAccount WHERE name = %s", (username,))
    result = cur.fetchone()

    if result:
        retailer_id = result[0]
        session_id = generate_unique_strings(1, 8)[0]
        session_password = generate_unique_strings(1, 8)[0]

        cur.execute("""
        INSERT INTO auth.sessionInfo VALUES (%s, %s, %s)
        """, (session_id, session_password, retailer_id))

        conn.commit()

        return { "id" : session_id, "password" : session_password }
    else:
        return None


def logout(session_id):
    """
    Perform the logout operation by deleting the session data from the authInfo table.

    Parameters:
    session_username (str): The session username to delete.

    Returns:
    bool: True if the session data was successfully deleted, otherwise False.
    """

    cur.execute("DELETE FROM auth.sessionInfo WHERE session_id = %s", (session_id,))

    if cur.rowcount > 0:
        conn.commit()
        success = True
    else:
        success = False

    return success


def lambda_handler(event, context):
    """
        Accept json requests and respond accordingly

        Parameters:
        event (json object): The request body.
        context (json object): null as of now

        Returns:
        json object: The response body.
    """
    retailer_id = authorize(event['session_id'], event['session_password'])
    while retailer_id is not None:
        if event['execution_mode'] == 'generate_licences':
            n = event['quantity']
            order_ids = generate_unique_strings(n, 24) # n temporary order ids
            licence_codes = generate_unique_strings(n, 5) # n licence codes
            cur.execute("""
            SELECT subclient_id 
            FROM baseschema.subclient 
            WHERE subclient_name = %s AND retailer_id = %s
            """, (event['tags']['subclient'], retailer_id))

            s_id = cur.fetchone()[0]

            while s_id is not None:
                for i in range(n):
                    cur.execute("""
                    INSERT INTO baseschema.Subscription(order_id, subclient_id, location) 
                    VALUES (%s, %s, %s)
                    """, (order_ids[i], s_id, event['tags']['location']))
                    cur.execute("""
                    INSERT INTO baseschema.Licence
                    VALUES (%s, %s, CURRENT_TIMESTAMP, %s)
                    """, (licence_codes[i], 'aaa-35-bb0' + str(i), order_ids[i]))
                conn.commit()
                return {
                    'msg': 'Ok',
                    'result_code': 'Licences generated'
                }
            else:
                return {
                    'msg' : 'Error',
                    'result_code' : 'Invalid subclient name'
                }
        elif event['execution_mode'] == 'list_licences':
            cur.execute("SELECT name FROM baseschema.retailerAccount WHERE retailer_id = %s", (retailer_id,))
            requested_by = cur.fetchone()[0]
            cur.execute("""
            SELECT licence_code, deeplink, created_at, location, subclient_name
            FROM baseschema.licence l, baseschema.subscription s, baseschema.subclient c, baseschema.retaileraccount r 
            WHERE l.order_id = s.order_id AND s.subclient_id = c.subclient_id AND c.retailer_id = (%s)""", (retailer_id,))
            tuples = cur.fetchall();
            s = set(tuples)
            ll = list()
            for i in s:
                d = {
                    "licence_code": i[0],
                    "licence_created_at_utc":i[2],
                    "tags": {
                        "requested_by": requested_by,
                        "subclient": i[4],
                        "location": i[3]
                    },
                    "activated_at_utc": False,
                    "deactivated_at_utc": None,
                    "last_seen_utc": None,
                    "billed_to_email": None,
                    "deeplink_data": i[1]
                }
                ll.append(d)
            return {
                "msg": "OK",
                "result_code": "licences_listed",
                "licences" : ll
            }
    else:
        print(event['session_id'], event['session_password'])
        return {
                    'msg' : 'Error',
                    'result_code' : 'Unauthorized'
                }



if __name__ == "__main__":
    username = input("Enter your username: ")
    session_info = login(username)
    print(json.dumps(session_info, indent=4))
    while True:
        ch = input("Enter your choice:\n1.Generate Licences\n2.List Licences\n3.Logout\n ")
        if ch == '1':
            with open('C:/Users/harsh/PycharmProjects/demoRun/test_event1.json', 'r') as f:
                event = json.load(f)
            event['session_id'] = session_info['id']
            event['session_password'] = session_info['password']
            event['tags']['requested_by'] = username;
            with open('C:/Users/harsh/PycharmProjects/demoRun/test_event1.json', 'w') as f:
                f.write(json.dumps(event, indent=4))
            response = lambda_handler(event, None);
            print(json.dumps(response, indent=4))
        elif ch == '2':
            with open('C:/Users/harsh/PycharmProjects/demoRun/test_event2.json', 'r') as f:
                event = json.load(f)
            event['session_id'] = session_info['id']
            event['session_password'] = session_info['password']
            with open('C:/Users/harsh/PycharmProjects/demoRun/test_event2.json', 'w') as f:
                f.write(json.dumps(event, indent=4))
            response = lambda_handler(event, None);
            print(json.dumps(response, indent=4, default=serialize_datetime))
        elif ch == '3':
            logout(session_info["id"])
            session_info = None
            break
        else:
            print("Invalid choice. Please re-enter")
    cur.close()
    conn.close()
