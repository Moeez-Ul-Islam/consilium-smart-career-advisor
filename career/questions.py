"""O*NET Mini Interest Profiler: 30 work-activity items, 5 per RIASEC type,
in the official administration order (interleaved R-I-A-S-E-C).

Items reproduced VERBATIM under the O*NET Career Exploration Tools Content
License (CC BY-ND 4.0). Source: Rounds, Wee, Cao, Song, & Lewis (2016),
"Development of an O*NET Mini Interest Profiler (Mini-IP) for Mobile
Devices", Appendix A (https://www.onetcenter.org/dl_files/Mini-IP.pdf).

Credit: This file includes information from the O*NET Career Exploration
Tools by the U.S. Department of Labor, Employment and Training
Administration (USDOL/ETA). Used under the CC BY-ND 4.0 license
(https://www.onetcenter.org/license_tools.html).
O*NET is a trademark of USDOL/ETA.
"""


QUESTIONS = [
    ('Build kitchen cabinets', 'R'),
    ('Develop a new medicine', 'I'),
    ('Write books or plays', 'A'),
    ('Help people with personal or emotional problems', 'S'),
    ('Manage a department within a large company', 'E'),
    ('Install software across computers on a large network', 'C'),
    ('Repair household appliances', 'R'),
    ('Study ways to reduce water pollution', 'I'),
    ('Compose or arrange music', 'A'),
    ('Give career guidance to people', 'S'),
    ('Start your own business', 'E'),
    ('Operate a calculator', 'C'),
    ('Assemble electronic parts', 'R'),
    ('Conduct chemical experiments', 'I'),
    ('Create special effects for movies', 'A'),
    ('Perform rehabilitation therapy', 'S'),
    ('Negotiate business contracts', 'E'),
    ('Keep shipping and receiving records', 'C'),
    ('Drive a truck to deliver packages to offices and homes', 'R'),
    ('Examine blood samples using a microscope', 'I'),
    ('Paint sets for plays', 'A'),
    ('Do volunteer work at a non-profit organization', 'S'),
    ('Market a new line of clothing', 'E'),
    ('Inventory supplies using a hand-held computer', 'C'),
    ('Test the quality of parts before shipment', 'R'),
    ('Develop a way to better predict the weather', 'I'),
    ('Write scripts for movies or television shows', 'A'),
    ('Teach a high-school class', 'S'),
    ('Sell merchandise at a department store', 'E'),
    ('Stamp, sort, and distribute mail for an organization', 'C'),
]


LIKERT_LABELS = [
    (1, 'Strongly Dislike'),
    (2, 'Dislike'),
    (3, 'Unsure'),
    (4, 'Like'),
    (5, 'Strongly Like'),
]


TEST_INSTRUCTION = (
    'For each work activity below, say how much you would enjoy doing it.'
)


ONET_CREDIT = (
    'Test items from the O*NET Interest Profiler by the U.S. Department of '
    'Labor, Employment and Training Administration (USDOL/ETA). '
    'Used under the CC BY-ND 4.0 license. O*NET is a trademark of USDOL/ETA.'
)
