import random
from typing import List, Optional, Tuple

from src.objects import Singer, Stage

StagePosition = Tuple[int, int, str]


def _choose_fallback_place(
    singer: Singer,
    available_places: List[StagePosition],
    stage: Stage,
) -> StagePosition:
    center_index = (stage.columns - 1) / 2
    own_block_indexes = {
        column
        for _, _, column, voice_part in stage.iter_places()
        if voice_part == singer.voice_part
    }

    def priority(position: StagePosition):
        _, column, _ = position
        block_distance = min(
            (abs(column - index) for index in own_block_indexes),
            default=abs(column - center_index),
        )
        return block_distance, -abs(column - center_index), position[0]

    best_priority = min(priority(place) for place in available_places)
    closest_places = [
        place for place in available_places
        if priority(place) == best_priority
    ]
    return random.choice(closest_places)


def _order_places_by_side(
    available_places: List[StagePosition],
    stage: Stage,
) -> List[StagePosition]:
    places_by_position = {
        (position[0], position[1]): position
        for position in available_places
    }
    center_index = (stage.columns - 1) / 2
    ordered_places = []
    prefer_left = random.choice((True, False))

    for row in range(stage.rows):
        left = sorted(
            (
                places_by_position[(row, column)]
                for column in range(stage.columns)
                if column < center_index and (row, column) in places_by_position
            ),
            key=lambda position: position[1],
        )
        right = sorted(
            (
                places_by_position[(row, column)]
                for column in range(stage.columns)
                if column > center_index and (row, column) in places_by_position
            ),
            key=lambda position: position[1],
            reverse=True,
        )
        center = (
            places_by_position.get((row, int(center_index)))
            if center_index.is_integer()
            else None
        )
        if center is not None:
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
    stage: Stage,
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
    positions = [
        (row, column, voice_part)
        for _, row, column, voice_part in stage.iter_places()
    ]
    available_places = [
        position for position in positions
        if stage.place_id(position[0], position[1]) not in occupied_place_ids
    ]
    matched_place_ids = set()

    for singer in singers_to_assign:
        singer.place_id = None

    for place in _order_places_by_side(
        available_places,
        stage,
    ):
        if not singers_to_assign:
            break
        matching_singers = [
            singer for singer in singers_to_assign
            if singer.voice_part == place[2]
        ]
        if not matching_singers:
            continue
        singer = random.choice(matching_singers)
        place_id = stage.place_id(place[0], place[1])
        singer.place_id = place_id
        singers_to_assign.remove(singer)
        matched_place_ids.add(place_id)

    unmatched_places = [
        place for place in available_places
        if stage.place_id(place[0], place[1]) not in matched_place_ids
    ]
    random.shuffle(singers_to_assign)
    for singer in singers_to_assign:
        if not unmatched_places:
            break
        place = _choose_fallback_place(
            singer,
            unmatched_places,
            stage,
        )
        singer.place_id = stage.place_id(place[0], place[1])
        unmatched_places.remove(place)
