AUTOMATA TM

template_id: TM_PALINDROME_ODD

pattern_family: {palindromes}

difficulty: 5

description:
Design a TM that accepts all palindromes of odd length over the given alphabet strings that read the same
forwards and backwards.  Only odd length strings are accepted 


alphabet:
    size: 2
    symbol_pools:{a,b,c}
                 {0,1}

roles:{
}

parameters:

condition: palindrome
    length % 2 == 1

testing:
    cases: 200
    max_length: 50

tags : { TM, palindrome, advanced }

closure_allowed: true
END