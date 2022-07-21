import asyncio
from kucoin_futures.client import WsToken
from kucoin_futures.ws_client import KucoinFuturesWsClient

key = '62d254194deedd0001e77cf3' #kucoin futures
secret = 'bfa00f13-7103-4e5a-890b-165b520cd77a'
passphrase = 'noatrader'
async def main():
    async def deal_msg(msg):
        print(msg)
        # if msg['topic'] == '/contractMarket/level2:XBTUSDM':
        #     print(f'Get XBTUSDM Ticker:{msg["data"]}')
        # elif msg['topic'] == '/contractMarket/level3:XBTUSDTM':
        #     print(f'Get XBTUSDTM level3:{msg["data"]}')

    # is public
    # client = WsToken()
    # is private
    client = WsToken(key=key, secret=secret, passphrase=passphrase, is_sandbox=False)
    # is sandbox
    # client = WsToken(is_sandbox=True)
    ws_client = await KucoinFuturesWsClient.create(loop, client, deal_msg, private=True)
    # await ws_client.subscribe('/contractMarket/level2:XBTUSDM')
    await ws_client.subscribe('/contract/position:XBTUSDTM')
    # await ws_client.subscribe('/contractMarket/level3:XBTUSDM')
    while True:
        await asyncio.sleep(60, loop=loop)


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())

# API keys
# api_key=""
# api_secret=""
# api_passphrase=""

# import asyncio
# from kucoin_futures.client import WsToken
# from kucoin_futures.ws_client import KucoinFuturesWsClient


# async def main():
#     async def deal_msg(msg):
#         if msg['topic'] == '/contract/position:XBTUSDM':
#             print(f'Position Change:{msg["data"]}')
        

 
#     client = WsToken(key=api_key, secret=api_secret, passphrase=api_passphrase, is_sandbox=False, url="https://api-futures.kucoin.com")
  

#     ws_client = await KucoinFuturesWsClient.create(loop, client, deal_msg, private=False)
#     await ws_client.subscribe('/contract/position:XBTUSDM')
#     while True:
#         await asyncio.sleep(60)


# if name == "main":
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(main())