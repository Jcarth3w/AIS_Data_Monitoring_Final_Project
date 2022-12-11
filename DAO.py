import json
import configparser
import mysql.connector
from mysql.connector import errorcode
import unittest 
import datetime
import csv


class MessageDAO:

	def __init__(self, test_mode=False):
		self.test_mode=test_mode
		self.Mysql_connector = Mysql_connector()


	#Function that takes a batch of AIS Messages OR a single AIS Message
	#And inserts it into the database
	#Can be either POSITION_REPORT or STATIC_DATA
	#Returns amount of rows inserted
	def insert_messages(self, batch):
		try:

			array = json.loads(batch)

			newarray = []
			if isinstance(array, dict):
				newarray.append(array)
				array = newarray

		except Exception as e:
			print(e)
			return -1

		if self.test_mode:
			return len(array)
			
		else:
			cnx = Mysql_connector.getConnection()

			cursor = cnx.cursor(prepared=True)

			cursor.execute("SELECT COUNT(*) FROM AIS_MESSAGE")
			initalrowcount = cursor.fetchall()[0][0]
			cursor.reset()

			for message in array:
				#extract all the AIS_MESSAGE  and add them to the ais_message list
				timeStamp = self.convert_time(message['Timestamp'])
				shipClass = message['Class']
				mmsi = message['MMSI']
				msgType = message['MsgType']
				cursor.execute("""INSERT INTO AIS_MESSAGE VALUES(%s, %s, %s, %s, %s, %s)""",
				list((None, datetime.datetime.fromisoformat(timeStamp), mmsi, shipClass, msgType, None)))
				#if the message type is static data, extract all of the fields for static data
				if msgType == "static_data":
					imo = message['IMO']
					if imo == 'Unknown':
						imo = None

					try:
						callsign = message['CallSign']

					except:
						callsign = None

					try:
						destination_id = message['Destination']
					except:
						destination_id = None

					cursor.execute("""INSERT INTO STATIC_DATA VALUES(LAST_INSERT_ID(), %s, %s, %s)""",
					list((imo, callsign, destination_id)))

				#if the message type is position report extract all the fields and add them to associated list
				elif msgType == "position_report":
					position = message['Position']
					coordinates = position['coordinates']
					latitude = coordinates[0]
					longitude = coordinates[1]
					status = message['Status']
					rot = message['RoT']
					sog = message['SoG']
					cog = message['CoG']
					heading = message['Heading']

					mapview3 = None
					mapview2 = None
					mapview1 = None


			cursor.reset()
			cnx.commit()
			cursor.execute("SELECT COUNT(*) FROM AIS_MESSAGE")
			rowcount = cursor.fetchall()[0][0]
			cnx.close()

			return abs(rowcount - initalrowcount)

	#Function that deletes entries in the AIS_MESSAGE table if their timestamp is more than 5 minutes old
	#The corresponding STATIC_DATA or POSITION_REPORT entry should also be deleted
	#Returns number of rows deleted
	def delete_msg_timestamp (self):
		if self.test_mode:
			deleted = [10] * 10

			return len(deleted)

		else:
			
			#Runs query through connection
			cnx = Mysql_connector.getConnection()

			cursor = cnx.cursor(prepared=True)

			cursor.execute("""DELETE AIS_MESSAGE FROM AIS_MESSAGE WHERE  AIS_MESSAGE.TS < (NOW() - INTERVAL 5 MINUTE);""")
			cnx.commit()

			return cursor.rowcount
			
			
	#Returns a list of ship documents in the form of (MMSI, Latitude, Longitude)
	def read_most_recent_positions(self):
		if self.test_mode:
			shipDocument = [100000000, 11.232, 55.888]
			return shipDocument

		else:
			
			#Runs query through connection
			cnx = Mysql_connector.getConnection()
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT DISTINCT(mmsi), ts, latitude, longitude FROM POSITION_REPORT as pr, AIS_MESSAGE as am WHERE pr.AISMessage_id=am.Id  ORDER BY ts DESC;""")

			returnedList = cursor.fetchall()
			
			#Removes unwanted field in table
			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list(returnedList[value])
				returnedList[value].pop(1)

				returnedList[value][1] = float(returnedList[value][1])
				returnedList[value][2] = float(returnedList[value][2])

			return returnedList

	#Function takes an integer MMSI value
	#Returns a list of ship documents in the form of (MMSI, IMO, Latitude, Longitude)
	def read_most_recent_positions_MMSI(self, mmsi):
		if self.test_mode:
			try:
				return int(mmsi)
			except:
				return -1

		else:
		
			#Runs query through connection
			cnx = Mysql_connector.getConnection()
			mmsiInQuery = []
			mmsiInQuery.append(mmsi)
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT ves.MMSI, IMO, Ts, Latitude, Longitude FROM POSITION_REPORT as pr, AIS_MESSAGE as am, VESSEL as ves WHERE am.MMSI=%s AND ves.MMSI=am.MMSI AND pr.AISMessage_id=am.Id ORDER BY Ts DESC LIMIT 1;""", mmsiInQuery)

			returnedList = cursor.fetchall()
			
			#Removes unwanted field in table
			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list(returnedList[value])
				returnedList[value].pop(2)

				returnedList[value][2] = float(returnedList[value][2])
				returnedList[value][3] = float(returnedList[value][3])

			return returnedList

	#Function takes an integer MMSI and IMO value
	#Returns the vessel data for the matching MMSI and IMO in the form (MMSI, IMO, Name, Latitude, Longitude)
	def read_permanent_info(self, MMSI, IMO):
		if self.test_mode:
			try:
				return int(MMSI)
			except:
				return -1
		else:
			
			#Runs query through connection
			valuesForQuery = []
			valuesForQuery.append(MMSI)
			valuesForQuery.append(IMO)
			cnx = Mysql_connector.getConnection()
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT ves.MMSI, IMO, Name, Latitude, Longitude FROM POSITION_REPORT as pr, VESSEL as ves, AIS_MESSAGE as am WHERE am.MMSI=ves.MMSI AND pr.AISMessage_id=am.Id AND ves.MMSI=%s AND ves.IMO=%s;""", valuesForQuery)

			returnedList = cursor.fetchall()

			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list((returnedList[value]))

				returnedList[value][3] = float(returnedList[value][3])
				returnedList[value][4] = float(returnedList[value][4])


			return returnedList


	
	#Function takes an integer Map Tile ID value
	#Returns a list of ship documents in the form of (MMSI, IMO, Latitude, Longitude)
	def read_most_recent_in_tile(self, tileID):
		if self.test_mode:
			try:
				return int(tileID)
			except:
				return -1
		else:
			#tile_id = []
			#tile_id.append(tileID)
			cnx = Mysql_connector.getConnection()
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT ves.MMSI, IMO, Latitude, Longitude FROM POSITION_REPORT as pr, AIS_MESSAGE as am, VESSEL as ves WHERE (pr.MapView1_Id=%s OR pr.MapView2_Id=%s OR pr.MapView3_Id=%s) AND ves.MMSI=am.MMSI AND pr.AISMessage_id=am.Id ORDER BY Ts DESC;""", list((tileID, tileID, tileID)))

			returnedList = cursor.fetchall()

			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list((returnedList[value]))

				returnedList[value][2] = float(returnedList[value][2])
				returnedList[value][3] = float(returnedList[value][3])


			return returnedList

	#Function takes string values Name and Country 
	#Returns a list of Port data matching parameters 
	#in the form (ID, LoCode, Name, Country, Longitude, Latitude, Mapview1_Id, Mapview2_Id, Mapview3_Id)
	def read_ports_with_name(self, name, country):
		if self.test_mode:
			try:
				return str(name)
			except:
				return -1

		else:
			#Runs query through connection
			valuesForQuery = []
			valuesForQuery.append(name)
			valuesForQuery.append(country)
			cnx = Mysql_connector.getConnection()
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT * FROM PORT WHERE Name=%s AND Country=%s;""", valuesForQuery)

			returnedList = cursor.fetchall()

			#Removes unwanted field in table
			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list((returnedList[value]))
				returnedList[value].pop(6)

				returnedList[value][4] = float(returnedList[value][4])
				returnedList[value][5] = float(returnedList[value][5])

			return returnedList

	#Function takes string values Port Name and Country
	#Return a list of ship documents in the form of (MMSI, IMO, Latitude, Longitude)
	def read_positions_tile3_port(self, port_name, country):
		if self.test_mode:
			try:
				return str(port_name)
			except:
				return -1

		else:
			#Runs query through connection
			valuesForQuery = []
			valuesForQuery.append(port_name)
			valuesForQuery.append(country)
			cnx = Mysql_connector.getConnection()
			cursor = cnx.cursor(prepared=True)
			cursor.execute("""SELECT ves.MMSI, IMO, pr.Latitude, pr.Longitude FROM PORT, POSITION_REPORT as pr, AIS_MESSAGE as am, VESSEL as ves WHERE PORT.Name=%s AND PORT.Country=%s AND pr.MapView3_Id=PORT.MapView3_Id AND ves.MMSI=am.MMSI AND pr.AISMessage_id=am.Id ORDER BY Ts DESC;""", valuesForQuery)

			returnedList = cursor.fetchall()

			#Converts Latitude and Longitude values into float values
			for value in range(len(returnedList)):
				returnedList[value] = list((returnedList[value]))

				returnedList[value][2] = float(returnedList[value][2])
				returnedList[value][3] = float(returnedList[value][3])

			return returnedList
			
	#Function takes an integer MMSI value
	#Returns a list of 5 ship documents in the form of (MMSI, IMO, Latitude, Longitude)
	def read_last_five_positions(self, mmsi):
		if self.test_mode:
			try:
				return int(mmsi)
			except:
				return -1 
		else:
		
			#Runs query through connection
        		mmsiInQuery = []
        		mmsiInQuery.append(mmsi)
        		cnx = Mysql_connector.getConnection()
        		cursor = cnx.cursor(prepared=True)
        		cursor.execute("""SELECT IMO, Latitude, Longitude FROM POSITION_REPORT as pr, AIS_MESSAGE as am, VESSEL as ves WHERE am.MMSI=%s AND ves.MMSI=am.MMSI AND pr.AISMessage_id=am.Id ORDER BY Ts DESC LIMIT 5;""", mmsiInQuery)
        		
        		returnedList = cursor.fetchall()
        		imo = 0
        		
        		#Removes unwanted field in table
			#Converts Latitude and Longitude values into float values
        		for value in range(len(returnedList)):
        			returnedLIst[value] = list(returnedList[value])
        			imo = retrunedList[value].pop(0)
        			
        			retrunedList[value][0] = float(returnedList[value][0])
        			returnedList[value][1] = float(returnedList[value][1])
        			
        		return dict({"MMSI": mmsi, "Positions": returnedList, "IMO": imo})

	#Converts timestamp values to work with mysql table insertion
	def convert_time(self, timestamp):
		return str(timestamp).replace('T',' ').replace('Z', '')


#connection class
class Mysql_connector():

	def __init__(self):
		pass

	
	def getConnection():
		config = configparser.ConfigParser()
		config.read('config.ini')
		try:
			return mysql.connector.connect(host = '127.0.0.1',
			user = config['mysqlDB']['user'],
			password = config['mysqlDB']['password'],
			db = config['mysqlDB']['db'],
			port = config['mysqlDB']['port'])

		except mysql.connector.Error as err:
			if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
				print("Something is wrong with your user name or password")
			elif err.erno == errorcode.ER_BAD_DB_ERROR:
				print("Database does not exist")
			else:
				print(err)



##################TESTS#####################


class DAOTest (unittest.TestCase):

	batch1 = """[ {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"AtoN\",\"MMSI\":992111840,\"MsgType\":\"static_data\",\"IMO\":\"Unknown\",\"Name\":\"WIND FARM BALTIC1NW\",\"VesselType\":\"Undefined\",\"Length\":60,\"Breadth\":60,\"A\":30,\"B\":30,\"C\":30,\"D\":30},
                {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"Class A\",\"MMSI\":219005465,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[54.572602,11.929218]},\"Status\":\"Under way using engine\",\"RoT\":0,\"SoG\":0,\"CoG\":298.7,\"Heading\":203},
                {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"Class A\",\"MMSI\":257961000,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[55.00316,12.809015]},\"Status\":\"Under way using engine\",\"RoT\":0,\"SoG\":0.2,\"CoG\":225.6,\"Heading\":240},
                {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"AtoN\",\"MMSI\":992111923,\"MsgType\":\"static_data\",\"IMO\":\"Unknown\",\"Name\":\"BALTIC2 WINDFARM SW\",\"VesselType\":\"Undefined\",\"Length\":8,\"Breadth\":12,\"A\":4,\"B\":4,\"C\":4,\"D\":8},
                {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"Class A\",\"MMSI\":257385000,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[55.219403,13.127725]},\"Status\":\"Under way using engine\",\"RoT\":25.7,\"SoG\":12.3,\"CoG\":96.5,\"Heading\":101},
                {\"Timestamp\":\"2023-11-18T00:00:00.000Z\",\"Class\":\"Class A\",\"MMSI\":376503000,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[54.519373,11.47914]},\"Status\":\"Under way using engine\",\"RoT\":0,\"SoG\":7.6,\"CoG\":294.4,\"Heading\":290} ]"""

	batch2 = """[{\"Timestamp\":\"2019-12-06T15:00:00.000Z\",\"Class\":\"AtoN\",\"MMSI\":992111840,\"MsgType\":\"static_data\",\"IMO\":\"Unknown\",\"Name\":\"WIND FARM BALTIC1NW\",\"VesselType\":\"Undefined\",\"Length\":60,\"Breadth\":60,\"A\":30,\"B\":30,\"C\":30,\"D\":30},
                {\"Timestamp\":\"2019-12-06T14:56:00.000Z\",\"Class\":\"Class A\",\"MMSI\":219005465,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[54.572602,11.929218]},\"Status\":\"Under way using engine\",\"RoT\":0,\"SoG\":0,\"CoG\":298.7,\"Heading\":203},
                {\"Timestamp\":\"2019-12-06T14:00:00.000Z\",\"Class\":\"Class A\",\"MMSI\":257961000,\"MsgType\":\"position_report\",\"Position\":{\"type\":\"Point\",\"coordinates\":[55.00316,12.809015]},\"Status\":\"Under way using engine\",\"RoT\":0,\"SoG\":0.2,\"CoG\":225.6,\"Heading\":240}]"""

	messageDocument = """{\"Timestamp\":\"2022-12-06T15:00:00.000Z\",\"Class\":\"AtoN\",\"MMSI\":9999999,\"MsgType\":\"static_data\",\"IMO\":\"Unknown\",\"Name\":\"YAHOOTEST\",\"VesselType\":\"Undefined\",\"Length\":60,\"Breadth\":60,\"A\":30,\"B\":30,\"C\":30,\"D\":30}"""


	#tests correct insertion type
	def test_insert_messages (self):
		dao = MessageDAO(True)
		inserted_messages = dao.insert_messages(self.batch1)
		self.assertTrue(type(inserted_messages) is int and inserted_messages > 0)

	#passes if insertion type is incorrect
	def test_insert_messages2 (self):
		dao = MessageDAO(True)
		array = json.loads( self.batch1 )
		inserted_count = dao.insert_messages( array )
		self.assertEqual( inserted_count, -1)

	#passes if timestampformat is correct
	def test_delete_msg_timeStamp (self):
		dao = MessageDAO(True)
		deleted = dao.delete_msg_timestamp()
		self.assertEqual(deleted, 10)


	def test_read_most_recent_positions(self):
		dao = MessageDAO(True)
		array = []
		result = dao.read_most_recent_positions()
		self.assertTrue(type(result) is type(array))

	def test_most_recent_pos_mmsi(self):
		dao = MessageDAO(True)
		result = dao.read_most_recent_positions_MMSI(3048580000)

		self.assertTrue(type(result) is int)

	def test_read_permanent_info(self):
		dao = MessageDAO(True)
		result = dao.read_permanent_info(3048580000, 9231535)
		self.assertTrue(type(result) is int)

	def test_read_ports_with_name(self):
		dao = MessageDAO(True)
		result = dao.read_ports_with_name("ABC", "Japan")
		self.assertTrue(type(result) is str)

	def test_most_recent_in_tile(self):
		dao = MessageDAO(True)
		result = dao.read_most_recent_in_tile(5361)
		self.assertTrue(type(result) is int)

	def test_read_positions_tile3_port(self):
		dao = MessageDAO(True)
		result = dao.read_positions_tile3_port("Aabenraa", "Denmark")
		self.assertTrue(type(result) is str)
		
	def test_

	def test_convert_time(self):
		dao = MessageDAO()
		convertedTime = "2020-11-18 00:00:00.000"
		self.assertEqual(convertedTime, dao.convert_time("2020-11-18T00:00:00.000Z"))


########Integration Tests###########

	def test_insert_messages3 (self):
		dao = MessageDAO()
		statements = dao.insert_messages(self.batch1)

		self.assertEqual(statements, 6)

	def test_insert_single_message(self):
		dao = MessageDAO()
		statements = dao.insert_messages(self.messageDocument)
		self.assertEqual(statements, 1)

	def test_delete_msg_timestamp2 (self):
		dao = MessageDAO()

		dao.insert_messages(self.batch2)
		deletedRows = dao.delete_msg_timestamp()

		self.assertEqual(deletedRows, 3)

	def test_read_most_recent_positions2 (self):
		dao = MessageDAO()
		resultArray = dao.read_most_recent_positions()
		self.assertEqual(list((219024178, 54.571808, 11.928697)), resultArray[0])
		self.assertEqual(list((219015362, 57.120712, 8.599567)), resultArray[1])

	def test_read_most_recent_pos_mmsi2(self):
		dao = MessageDAO()
		testMMSI = 304858000
		resultArray = dao.read_most_recent_positions_MMSI(testMMSI)
		self.assertEqual(list((304858000, 8214358, 55.21829, 13.372545)), resultArray[0])

	def test_read_permanent_info2(self):
		dao = MessageDAO()
		testMMSI = 304858000
		testIMO = 8214358
		resultArray = dao.read_permanent_info(testMMSI, testIMO)
		self.assertEqual(list((304858000, 8214358, 'St.Pauli', 55.21829, 13.372545)), resultArray[0])

	def test_read_port_with_name2(self):
		dao = MessageDAO()
		expectedArray = [[381, 'DKNBG', 'Nyborg', 'Denmark', 10.810833, 55.298889, 1, 5331, 53312],
		[4970, None, 'Nyborg', 'Denmark', 10.790833, 55.306944, 1, 5331, 53312]]
		resultArray = dao.read_ports_with_name('Nyborg', 'Denmark')
		self.assertEqual(expectedArray, resultArray)

	def test_most_recent_in_tile2(self):
		dao = MessageDAO()
		expectedArray = [[220043000, 4026519, 57.120583, 8.599218],[220043000, 8996413, 57.120583, 8.599218]]
		resultArray = dao.read_most_recent_in_tile(5139)
		self.assertEqual(expectedArray, resultArray)

	def test_read_positions_tile3_port2(self):
		dao = MessageDAO()
		expectedArray = [[219000647, 9080132, 55.04231, 9.423348]]
		resultArray = dao.read_positions_tile3_port("Aabenraa", "Denmark")
		self.assertEqual(expectedArray, resultArray)



unittest.main()











