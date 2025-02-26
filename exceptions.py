from fastapi import HTTPException
from starlette import status


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


ws_unauthorized_none_access = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail='Требуется авторизация.'
)


not_found_table = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail='Стол не найден'
)