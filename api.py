import aiohttp
import config

class FatherSMM:
    def __init__(self):
        self.url = config.SMM_API_URL
        self.key = config.SMM_API_KEY

    async def _request(self, params):
        params["key"] = self.key
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.url, data=params) as resp:
                    return await resp.json()
            except Exception as e:
                return {"error": str(e)}

    async def get_services(self):
        return await self._request({"action": "services"})

    async def add_order(self, service_id, link, quantity):
        return await self._request({
            "action": "add",
            "service": service_id,
            "link": link,
            "quantity": quantity
        })

    async def get_status(self, order_id):
        return await self._request({
            "action": "status",
            "order": order_id
        })

smm = FatherSMM()
