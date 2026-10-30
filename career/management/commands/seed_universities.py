from django.core.management.base import BaseCommand
from career.models import University

SEED = [

    ('FAST-NUCES', 'Lahore', 'BS Computer Science, BS Software Engineering, BS AI', 'cs', 'https://www.nu.edu.pk'),
    ('NUST', 'Islamabad', 'BS Computer Science, BS Software Engineering', 'cs', 'https://www.nust.edu.pk'),
    ('COMSATS University', 'Islamabad', 'BS Computer Science, BS Software Engineering', 'cs', 'https://www.comsats.edu.pk'),
    ('LUMS', 'Lahore', 'BS Computer Science', 'cs', 'https://www.lums.edu.pk'),

    ('King Edward Medical University', 'Lahore', 'MBBS, BDS, Nursing', 'medicine', 'https://www.kemu.edu.pk'),
    ('Aga Khan University', 'Karachi', 'MBBS, BDS, Nursing', 'medicine', 'https://www.aku.edu'),
    ('Dow University of Health Sciences', 'Karachi', 'MBBS, BDS, Pharm-D', 'medicine', 'https://www.duhs.edu.pk'),
    ('University of Health Sciences', 'Lahore', 'MBBS, BDS, Pharm-D', 'medicine', 'https://www.uhs.edu.pk'),

    ('NUST', 'Islamabad', 'BS Electrical, BS Mechanical, BS Civil Engineering', 'engineering', 'https://www.nust.edu.pk'),
    ('UET Lahore', 'Lahore', 'BS Electrical, BS Mechanical, BS Civil Engineering', 'engineering', 'https://www.uet.edu.pk'),
    ('GIKI', 'Topi', 'BS Electrical, BS Mechanical, BS Computer Engineering', 'engineering', 'https://www.giki.edu.pk'),
    ('NED University', 'Karachi', 'BS Electrical, BS Mechanical, BS Civil Engineering', 'engineering', 'https://www.neduet.edu.pk'),

    ('IBA Karachi', 'Karachi', 'BBA, BS Accounting & Finance', 'business', 'https://www.iba.edu.pk'),
    ('LUMS', 'Lahore', 'BBA, BS Accounting & Finance', 'business', 'https://www.lums.edu.pk'),
    ('SZABIST', 'Karachi', 'BBA, BS Accounting & Finance', 'business', 'https://www.szabist.edu.pk'),
    ('IoBM', 'Karachi', 'BBA, BS Accounting & Finance', 'business', 'https://www.iobm.edu.pk'),

    ('University of the Punjab', 'Lahore', 'BS Psychology, BS Mass Communication, LLB', 'arts', 'https://www.pu.edu.pk'),
    ('University of Karachi', 'Karachi', 'BS Psychology, BS Mass Communication', 'arts', 'https://www.uok.edu.pk'),
    ('BZU Multan', 'Multan', 'BS Psychology, BS Mass Communication, LLB', 'arts', 'https://www.bzu.edu.pk'),
    ('GC University Lahore', 'Lahore', 'BS Psychology, LLB', 'arts', 'https://www.gcu.edu.pk'),
    ('Pakistan Institute of Fashion and Design', 'Lahore', 'BFD Fashion Design, BS Textile Design, BFA', 'arts', 'https://www.pifd.edu.pk'),
    ('Indus Valley School of Art and Architecture', 'Karachi', 'BFA Fine Arts, BS Textile Design', 'arts', 'https://www.indusvalley.edu.pk'),
    ('Beaconhouse National University', 'Lahore', 'BFA, BS Media Studies, BS Psychology', 'arts', 'https://www.bnu.edu.pk'),
    ('University of Home Economics', 'Lahore', 'BS Home Economics, BS Sports Sciences', 'arts', 'https://www.uhe.edu.pk'),
]


class Command(BaseCommand):
    help = 'Seed default universities into the database.'

    def handle(self, *args, **options):
        created = 0
        for name, city, programs, category, website in SEED:
            _, was_created = University.objects.get_or_create(
                name=name, city=city, career_category=category,
                defaults={'programs': programs, 'website': website})
            if was_created:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Seeded {created} new universities.'))
