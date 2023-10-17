# Copyright (c) 2022 Robert Bosch GmbH and Microsoft Corporation
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""A sample skeleton vehicle app."""

import asyncio
import json
import logging
import signal

from vehicle import Vehicle, vehicle  # type: ignore
from velocitas_sdk.util.log import (  # type: ignore
    get_opentelemetry_log_factory,
    get_opentelemetry_log_format,
)
from velocitas_sdk.vdb.reply import DataPointReply  # type: ignore
from velocitas_sdk.vehicle_app import VehicleApp, subscribe_topic  # type: ignore

# Configure the VehicleApp logger with the necessary log config and level.
logging.setLogRecordFactory(get_opentelemetry_log_factory())
logging.basicConfig(format=get_opentelemetry_log_format())
logging.getLogger().setLevel("DEBUG")
logger = logging.getLogger(__name__)

CURRENT_POSITION_TOPIC = "seatadjuster/currentPosition"
SET_POSITION_REQUEST_TOPIC = "seatadjuster/setPosition/request"
SET_POSITION_RESPONSE_TOPIC = "seatadjuster/setPosition/response"


class SeatAdjusterApp(VehicleApp):
    """
    seadjuster app
    """

    def __init__(self, vehicle_client: Vehicle):
        super().__init__()
        self.Vehicle = vehicle_client

    async def on_start(self):
        """Run when the vehicle app starts"""
        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.subscribe(
            self.on_seat_position_change
        )

    async def on_seat_position_change(self, data: DataPointReply) -> None:
        """The on_seat_position_change callback, this will be executed when receiving
        a new vehicle signal updates."""

        current_position = data.get(self.Vehicle.Cabin.Seat.Row1.Pos1.Position).value
        await self.publish_event(
            CURRENT_POSITION_TOPIC,
            json.dumps({"position": current_position}),
        )

    @subscribe_topic(SET_POSITION_REQUEST_TOPIC)
    async def on_set_position_request(self, mqtt_data_str: str) -> None:
        mqtt_request_data = json.loads(mqtt_data_str)

        vehicle_speed = (await self.Vehicle.Speed.get()).value
        position = mqtt_request_data["position"]
        response = {}
        if vehicle_speed == 0:
            try:
                await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(position)
                response = {"status": 0, "message": f"Set position to {position}"}
            except ValueError as err:
                response = {
                    "status": 1,
                    "message": f"Failed to set position to {position}, error: {err}",
                }
            except Exception as err:
                response = {
                    "status": 1,
                    "message": f"Failed to set position to {position}, error: {err}",
                }
        else:
            error_msg = f"""Not allowed to move seat because vehicle speed
                is {vehicle_speed} and not 0"""
            response["result"] = {"status": 1, "message": error_msg}

        response_message = {
            "requestId": mqtt_request_data["requestId"],
            "result": response,
        }

        await self.publish_event(
            SET_POSITION_RESPONSE_TOPIC, json.dumps(response_message)
        )
