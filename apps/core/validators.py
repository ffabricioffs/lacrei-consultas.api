"""Validadores de documentos brasileiros (CPF e CNPJ)."""

from apps.core.sanitizers import only_digits


def _todos_iguais(digits: str) -> bool:
    return len(set(digits)) == 1


def cpf_valido(value: str) -> bool:
    cpf = only_digits(value)
    if len(cpf) != 11 or _todos_iguais(cpf):
        return False
    for posicao in (9, 10):
        soma = sum(int(cpf[i]) * ((posicao + 1) - i) for i in range(posicao))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[posicao]):
            return False
    return True


def cnpj_valido(value: str) -> bool:
    cnpj = only_digits(value)
    if len(cnpj) != 14 or _todos_iguais(cnpj):
        return False
    pesos_1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos_2 = [6, *pesos_1]
    for pesos, posicao in ((pesos_1, 12), (pesos_2, 13)):
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(posicao))
        resto = soma % 11
        digito = 0 if resto < 2 else 11 - resto
        if digito != int(cnpj[posicao]):
            return False
    return True


def cpf_ou_cnpj_valido(value: str) -> bool:
    digits = only_digits(value)
    if len(digits) == 11:
        return cpf_valido(digits)
    if len(digits) == 14:
        return cnpj_valido(digits)
    return False
