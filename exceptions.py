from fastapi import HTTPException, WebSocketException
from starlette import status

import json


# HTTP


server_exc = HTTPException(
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    detail='Непредвиденная серверная ошибка. Попробуйте позже.'
)


bad_email_exc = HTTPException(
    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    detail='Email некорректен. Введите действительный адрес электронной почты.'
)


bad_token_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED, 
    detail=f'Неверный токен.'
)


not_found_access_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Access токен не найден в куки."
)


not_found_refresh_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Refresh токен не найден в куки."
)


not_found_token_user_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Неверный токен (пользователь не найден).'
)


unauthed_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Неверный логин или пароль."
)


conflict_name = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail='Данное имя пользователя уже используется. Попробуйте другое.'
)


bad_blinds = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Слишком маленькие значения. Увеличьте сумму."
)


bad_big_blind_small_count = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail="Big Blind может быть максимум в 2 раза меньше стартовой суммы."
)


bad_big_blind_uneven = HTTPException(
    status_code=status.HTTP_400_BAD_REQUEST,
    detail='Big Blind должен быть целым числом.'
)


conflict_table = HTTPException(
    status_code=status.HTTP_409_CONFLICT,
    detail='Данное название стола уже используется. Попробуйте другое.'
)


not_found_table = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail='Стол не найден'
)


min_players = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail='Необходимо минимум 2 игрока для начала игры.'
)


# WS


ws_server_exc = WebSocketException(
    code=status.WS_1011_INTERNAL_ERROR,
    reason='Непредвиденная серверная ошибка. Попробуйте позже.'
)


ws_unauthorized_none_access = WebSocketException(
    code=status.WS_1008_POLICY_VIOLATION,
    reason='Требуется авторизация.'
)


ws_not_found_table = WebSocketException(
    code=status.WS_1008_POLICY_VIOLATION,
    reason='Стол не найден.'
)


ws_max_players = WebSocketException(
    code=status.WS_1008_POLICY_VIOLATION,
    reason='За данным столом уже находится максимальное количество игроков.'
)


# WS (строки)


not_enough_funds_for_big_blind = json.dumps({"error": "Недостаточно средств для большого блайнда."})

not_enough_funds_for_small_blind = json.dumps({"error": "Недостаточно средств для малого блайнда."})

not_enough_funds_for_call = json.dumps({"error": "Недостаточно средств для call."})

twice_raise = json.dumps({"error": "Raise должен быть не меньше, чем двойной размер большого блайнда."})

raise_less_than_old = json.dumps({"error": "Ваш raise должен быть выше, чем raise другого игрока."})

not_enough_funds_for_raise = json.dumps({"error": "Недостаточно средств для raise."})

wrong_amount_for_raise = json.dumps({"error": "Неверная сумма для raise."})

player_folded = json.dumps({"error": "Вы больше не участвуете в этом раунде."})

other_turn = json.dumps({"error": "Не ваш ход!"})

check_done = json.dumps({"info": "Сделан check."})