import websockets
import requests
import json
import time




class GetStockData: 

    def __init__(self, api_key: str):
        
        self.api_key = api_key
                      

    def get_historical_stock_data(self, interval: str = "1day", symbols: list = ["VOO"], start_date: str = "2021-01-01", end_date: str = "2021-12-31"): 

        interval_allowed_list = ["1min", "1h", "1day", "1week", "1month"]
        if interval not in interval_allowed_list:
            raise ValueError(f"Invalid interval. Allowed intervals are: {', '.join(interval_allowed_list)}")

        responses_list = []
        # Format of date in "yyyy-mm-dd"
        for symbol in symbols:

            url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={interval}&start_date={start_date}&end_date={end_date}&apikey={self.api_key}"
            
            retry_num = 1

            max_retry_num = 3

            while (retry_num <= max_retry_num):
            
                response = requests.get(url)

                # Parse the JSON data
                data = response.json()
                # Check if the request was successful
                if response.status_code == 200 and 'meta' in data and data.get('status') == 'ok':

                    # Check the structure of the JSON response
                    print(f"data saved for symbol {symbol} and date range {start_date} to {end_date}.")
                    responses_list.append(data)
                    break
                    
                else:
                    print(f"No data found in the JSON response for symbol {symbol} and date range {start_date} to {end_date} for try # {retry_num}. " + "Waiting 61 sec. and retrying again.." if retry_num + 1 <= max_retry_num else ""  )

                retry_num += 1
                time.sleep(61)
                pass

        return responses_list

    # Subscribe to the WebSocket to get prices in real time
    async def subscribe_to_websocket():
        # Replace {$route} with the appropriate route (e.g., "price", "timeseries", etc.)
        route = "quotes/price"  # Replace with your route
        api_key = "23c1a7c2da0148c584eac977ac756432"  # Replace with your actual API key
        uri = f"wss://ws.twelvedata.com/v1/{route}?apikey={api_key}"

        async with websockets.connect(uri) as websocket:
            # Create the subscription message
            subscription_message = {
                "action": "subscribe",
                "params": {
                    "symbols": "AAPL,INFY,TRP,QQQ,IXIC,EUR/USD,USD/JPY,BTC/USD"
                }
            }

            # Send the subscription message
            await websocket.send(json.dumps(subscription_message))
            print(f"Sent: {subscription_message}")

            # Receive messages from the WebSocket
            while True:
                response = await websocket.recv() 
                response_json = json.loads(response)
                print(f"Received: { json.dumps(response_json, indent=4) }")

    # Run the subscription function
    # await subscribe_to_websocket()




