import random
from typing import List, Optional

from src.objects import Place, Singer


def _choose_fallback_place(
    singer: Singer,
    available_places: List[Place],
    places: List[Place],
    stage_columns: int,
) -> Place:
    center_index = (stage_columns - 1) / 2
    own_block_indexes = {
        place.index for place in places
        if place.voice_part == singer.voice_part
    }

    def priority(place: Place):
        block_distance = min(
            (abs(place.index - index) for index in own_block_indexes),
            default=abs(place.index - center_index),
        )
        return block_distance, -abs(place.index - center_index), place.row

    best_priority = min(priority(place) for place in available_places)
    closest_places = [
        place for place in available_places
        if priority(place) == best_priority
    ]
    return random.choice(closest_places)


def _order_places_by_side(
    available_places: List[Place],
    stage_rows: int,
    stage_columns: int,
) -> List[Place]:
    places_by_position = {
        (place.row, place.index): place
        for place in available_places
    }
    center_index = (stage_columns - 1) / 2
    ordered_places = []
    prefer_left = random.choice((True, False))

    for row in range(stage_rows):
        left = sorted(
            (
                places_by_position[(row, column)]
                for column in range(stage_columns)
                if column < center_index and (row, column) in places_by_position
            ),
            key=lambda place: place.index,
        )
        right = sorted(
            (
                places_by_position[(row, column)]
                for column in range(stage_columns)
                if column > center_index and (row, column) in places_by_position
            ),
            key=lambda place: place.index,
            reverse=True,
        )
        center = places_by_position.get((row, int(center_index)))
        if center is not None and center_index.is_integer():
            ordered_places.append(center)

        while left or right:
            if prefer_left and left:
                ordered_places.append(left.pop(0))
            elif right:
                ordered_places.append(right.pop(0))
            else:
                ordered_places.append(left.pop(0))
            prefer_left = not prefer_left

    return ordered_places


def assign_singer_places(
    singers: List[Singer],
    places: List[Place],
    stage_rows: int,
    stage_columns: int,
    singers_to_assign: Optional[List[Singer]] = None,
) -> None:
    if singers_to_assign is None:
        singers_to_assign = [singer for singer in singers if not singer.locked]
    else:
        singers_to_assign = singers_to_assign.copy()

    assigning_ids = {id(singer) for singer in singers_to_assign}
    occupied_place_ids = {
        singer.place_id
        for singer in singers
        if id(singer) not in assigning_ids and singer.place_id is not None
    }
    available_places = [
        place for place in places
        if place.id not in occupied_place_ids
    ]
    matched_place_ids = set()

    for singer in singers_to_assign:
        singer.place_id = None

    for place in _order_places_by_side(
        available_places,
        stage_rows,
        stage_columns,
    ):
        if not singers_to_assign:
            break
        matching_singers = [
            singer for singer in singers_to_assign
            if singer.voice_part == place.voice_part
        ]
        if not matching_singers:
            continue
        singer = random.choice(matching_singers)
        singer.place_id = place.id
        singers_to_assign.remove(singer)
        matched_place_ids.add(place.id)

    unmatched_places = [
        place for place in available_places
        if place.id not in matched_place_ids
    ]
    random.shuffle(singers_to_assign)
    for singer in singers_to_assign:
        if not unmatched_places:
            break
        place = _choose_fallback_place(
            singer,
            unmatched_places,
            places,
            stage_columns,
        )
        singer.place_id = place.id
        unmatched_places.remove(place)
